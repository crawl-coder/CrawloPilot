"""add memory_limit/cpu_limit to task_instance

Revision ID: c1r2a3w4l5o
Revises: u3s4e5r6m7a8
Create Date: 2026-08-07 18:00:00.000000

任务实例记录 Docker 资源限制，使重试可保留原任务资源语义。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1r2a3w4l5o'
down_revision: Union[str, None] = 'u3s4e5r6m7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('task_instance', sa.Column('memory_limit', sa.String(16), nullable=True))
    op.add_column('task_instance', sa.Column('cpu_limit', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('task_instance', 'cpu_limit')
    op.drop_column('task_instance', 'memory_limit')
