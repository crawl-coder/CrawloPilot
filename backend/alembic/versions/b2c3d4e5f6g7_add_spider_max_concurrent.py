"""add max_concurrent to spider (B2)

Revision ID: b2c3d4e5f6g7
Revises: a7b8c9d0e1f2
Create Date: 2026-08-24 20:00:00.000000

爬虫级并发上限：同一爬虫同时运行的任务数上限（默认 1，0=不限）。
手动运行、调度触发、run-now 统一受此守卫约束。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        res = bind.execute(
            sa.text("SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='spider' "
                    "AND COLUMN_NAME='max_concurrent'")).scalar()
        if res > 0:
            return
    op.add_column('spider', sa.Column('max_concurrent', sa.Integer(), server_default='1', nullable=False))


def downgrade() -> None:
    op.drop_column('spider', 'max_concurrent')
