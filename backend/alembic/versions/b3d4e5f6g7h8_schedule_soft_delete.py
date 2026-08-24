"""soft-delete schedules (B3)

Revision ID: b3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-08-24 21:00:00.000000

调度软删除：schedule 表新增 deleted_at 列（DateTime nullable）。
删除调度改为设置 deleted_at=now()，不删行、不置空任务 schedule_id，
保留任务与调度的历史关联。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b3d4e5f6g7h8'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        res = bind.execute(
            sa.text("SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='schedule' "
                    "AND COLUMN_NAME='deleted_at'")).scalar()
        if res > 0:
            return
    op.add_column('schedule', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('schedule', 'deleted_at')
