"""add task_instance fields for local execution

Revision ID: c1d2e3f4a5b6
Revises: 4a8c26e16402
Create Date: 2026-04-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = '4a8c26e16402'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 修改 schedule_id 为可空（手动执行时无调度）
    op.alter_column('task_instance', 'schedule_id',
                    existing_type=mysql.BIGINT(display_width=20),
                    nullable=True)
    
    # 修改 spider_name 为可空
    op.alter_column('task_instance', 'spider_name',
                    existing_type=sa.String(128),
                    nullable=True)
    
    # 添加新字段（pages_crawled/items_scraped/errors_count 已存在于数据库中）
    op.add_column('task_instance', sa.Column('process_id', sa.Integer(), nullable=True))
    op.add_column('task_instance', sa.Column('duration', sa.DECIMAL(10, 2), nullable=True))
    op.add_column('task_instance', sa.Column('error_message', sa.Text(), nullable=True))


def downgrade() -> None:
    # 删除新字段
    op.drop_column('task_instance', 'error_message')
    op.drop_column('task_instance', 'duration')
    op.drop_column('task_instance', 'process_id')
    
    # 恢复 schedule_id 为不可空
    op.alter_column('task_instance', 'schedule_id',
                    existing_type=mysql.BIGINT(display_width=20),
                    nullable=False)
    
    # 恢复 spider_name 为不可空
    op.alter_column('task_instance', 'spider_name',
                    existing_type=sa.String(128),
                    nullable=False)
