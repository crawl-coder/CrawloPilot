"""add distribution_mode fields to task_instance (D4)

Revision ID: d4e5f6g7h8i9
Revises: c1d2e3f4g5h6
Create Date: 2026-08-24 23:00:00.000000

task_instance 新增分布式模式字段：
- distribution_mode: standalone / single_node_distributed / multi_node_distributed
- shared_redis_url: 模式 C 共享 Redis 地址
- worker_count: 每节点 Worker 进程数
- redis_namespace: Crawlo Redis Key 命名空间
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, None] = 'c1d2e3f4g5h6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    def _col_exists(col):
        if dialect == "mysql":
            return bind.execute(sa.text(
                f"SELECT COUNT(*) FROM information_schema.COLUMNS "
                f"WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='task_instance' "
                f"AND COLUMN_NAME='{col}'")).scalar() > 0
        return False

    if not _col_exists('distribution_mode'):
        op.add_column('task_instance', sa.Column('distribution_mode', sa.String(32), server_default='standalone'))
    if not _col_exists('shared_redis_url'):
        op.add_column('task_instance', sa.Column('shared_redis_url', sa.String(256), nullable=True))
    if not _col_exists('worker_count'):
        op.add_column('task_instance', sa.Column('worker_count', sa.Integer, server_default='1'))
    if not _col_exists('redis_namespace'):
        op.add_column('task_instance', sa.Column('redis_namespace', sa.String(128), nullable=True))


def downgrade() -> None:
    for col in ('redis_namespace', 'worker_count', 'shared_redis_url', 'distribution_mode'):
        op.drop_column('task_instance', col)
