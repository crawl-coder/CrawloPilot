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
revision = 'c1d2e3f4a5b6'
down_revision = '4a8c26e16402'
branch_labels = None
depends_on = None


def _dialect() -> str:
    return op.get_bind().dialect.name.lower()


def upgrade() -> None:
    dialect = _dialect()

    def _set_nullable(col: str, col_type, nullable: bool):
        if dialect.startswith('sqlite'):
            with op.batch_alter_table('task_instance') as batch_op:
                batch_op.alter_column(col, existing_type=col_type, nullable=nullable)
        else:
            op.alter_column('task_instance', col, existing_type=col_type, nullable=nullable)

    # 修改 schedule_id 为可空（手动执行时无调度）
    _set_nullable('schedule_id', mysql.BIGINT(display_width=20), nullable=True)

    # 修改 spider_name 为可空
    _set_nullable('spider_name', sa.String(128), nullable=True)

    def _add_col_if_missing(col_name, col_def):
        from sqlalchemy import inspect
        insp = inspect(op.get_bind())
        cols = {c['name'] for c in insp.get_columns('task_instance')}
        if col_name in cols:
            return
        if dialect.startswith('sqlite'):
            with op.batch_alter_table('task_instance') as batch_op:
                batch_op.add_column(col_def)
        else:
            op.add_column('task_instance', col_def)

    _add_col_if_missing('process_id', sa.Column('process_id', sa.Integer(), nullable=True))
    _add_col_if_missing('duration', sa.Column('duration', sa.DECIMAL(10, 2), nullable=True))
    _add_col_if_missing('error_message', sa.Column('error_message', sa.Text(), nullable=True))


def downgrade() -> None:
    dialect = _dialect()

    def _drop_col(col_name):
        if dialect.startswith('sqlite'):
            with op.batch_alter_table('task_instance') as batch_op:
                batch_op.drop_column(col_name)
        else:
            op.drop_column('task_instance', col_name)

    _drop_col('error_message')
    _drop_col('duration')
    _drop_col('process_id')

    def _set_nullable(col: str, col_type, nullable: bool):
        if dialect.startswith('sqlite'):
            with op.batch_alter_table('task_instance') as batch_op:
                batch_op.alter_column(col, existing_type=col_type, nullable=nullable)
        else:
            op.alter_column('task_instance', col, existing_type=col_type, nullable=nullable)

    _set_nullable('schedule_id', mysql.BIGINT(display_width=20), nullable=False)
    _set_nullable('spider_name', sa.String(128), nullable=False)
