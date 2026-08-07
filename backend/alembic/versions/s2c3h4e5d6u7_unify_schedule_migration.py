"""unify schedule migration into alembic (absorbs migrate_schedule.py)

Revision ID: s2c3h4e5d6u7
Revises: g1c2r3e4d5s6
Create Date: 2026-08-07 14:00:00.000000

吸收原 backend/migrate_schedule.py 的全部职责（该脚本已删除，迁移机制统一回 alembic）：
- schedule 表补齐调度字段（spider_id/name/run_at/timezone/last_run_*/run_count/description/created_by）
- 存量 schedule 按 spider_name 回填 spider_id，未匹配的置为禁用
- task_instance 增加 expected_run_at + (schedule_id, expected_run_at) 唯一索引（触发幂等）

所有 DDL 均做存在性检查，对已应用过 migrate_schedule.py 的库可安全空跑。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = 's2c3h4e5d6u7'
down_revision: Union[str, None] = 'g1c2r3e4d5s6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(conn, table: str) -> set:
    return {c["name"] for c in inspect(conn).get_columns(table)}


def _existing_indexes(conn, table: str) -> set:
    return {i["name"] for i in inspect(conn).get_indexes(table)}


def upgrade() -> None:
    conn = op.get_bind()

    # 1) schedule 表补齐字段
    cols = _existing_columns(conn, "schedule")
    additions = [
        ("spider_id", sa.BigInteger()),
        ("spider_name", sa.String(128)),
        ("run_at", sa.DateTime()),
        ("timezone", sa.String(64)),
        ("last_run_at", sa.DateTime()),
        ("last_run_status", sa.String(16)),
        ("last_run_task_id", sa.BigInteger()),
        ("run_count", sa.Integer()),
        ("success_count", sa.Integer()),
        ("fail_count", sa.Integer()),
        ("description", sa.String(256)),
        ("created_by", sa.BigInteger()),
    ]
    with op.batch_alter_table("schedule") as batch:
        for name, col_type in additions:
            if name not in cols:
                batch.add_column(sa.Column(name, col_type, nullable=True))

    # 2) 回填 spider_id（仅处理 NULL 行，幂等；子查询写法跨方言）
    op.execute(text(
        "UPDATE schedule SET spider_id = ("
        "  SELECT id FROM spider WHERE spider.name = schedule.spider_name"
        ") WHERE spider_id IS NULL"
    ))
    # 未匹配的调度置为禁用，避免误触发
    op.execute(text(
        "UPDATE schedule SET enabled = 0 WHERE spider_id IS NULL"
    ))

    # 3) task_instance 幂等字段与唯一索引
    ti_cols = _existing_columns(conn, "task_instance")
    if "expected_run_at" not in ti_cols:
        with op.batch_alter_table("task_instance") as batch:
            batch.add_column(sa.Column("expected_run_at", sa.DateTime(), nullable=True))

    ti_indexes = _existing_indexes(conn, "task_instance")
    if "uq_task_schedule_expected" not in ti_indexes:
        op.create_index(
            "uq_task_schedule_expected", "task_instance",
            ["schedule_id", "expected_run_at"], unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()

    ti_indexes = _existing_indexes(conn, "task_instance")
    if "uq_task_schedule_expected" in ti_indexes:
        op.drop_index("uq_task_schedule_expected", table_name="task_instance")

    ti_cols = _existing_columns(conn, "task_instance")
    if "expected_run_at" in ti_cols:
        with op.batch_alter_table("task_instance") as batch:
            batch.drop_column("expected_run_at")

    cols = _existing_columns(conn, "schedule")
    with op.batch_alter_table("schedule") as batch:
        for name in ("created_by", "description", "fail_count", "success_count",
                     "run_count", "last_run_task_id", "last_run_status", "last_run_at",
                     "timezone", "run_at", "spider_name", "spider_id"):
            if name in cols:
                batch.drop_column(name)
