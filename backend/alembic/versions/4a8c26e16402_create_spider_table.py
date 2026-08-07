"""create spider table

Revision ID: 4a8c26e16402
Revises: b6985578c953
Create Date: 2026-04-11 23:38:52.607220

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a8c26e16402'
down_revision: Union[str, None] = '7c6c3df56972'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 与 b6985578c953 并行分支：两处都会建 spider 表/加 spider_id，
    # 幂等处理保证全新库 upgrade head 不重复建表报错。
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table('spider'):
        op.create_table(
            'spider',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('name', sa.String(128), nullable=False, index=True),
            sa.Column('project_id', sa.BigInteger(), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('spider_type', sa.String(32), nullable=True),
            sa.Column('status', sa.String(32), nullable=True),
            sa.Column('git_url', sa.String(512)),
            sa.Column('git_auth_type', sa.String(32)),
            sa.Column('git_username', sa.String(128)),
            sa.Column('git_password', sa.String(256)),
            sa.Column('git_ssh_key', sa.Text()),
            sa.Column('git_passphrase', sa.String(256)),
            sa.Column('git_branch', sa.String(128)),
            sa.Column('code_path', sa.String(512)),
            sa.Column('entry_file', sa.String(256)),
            sa.Column('config', sa.JSON()),
            sa.Column('schedule_config', sa.JSON()),
            sa.Column('last_run_at', sa.DateTime()),
            sa.Column('last_run_status', sa.String(32)),
            sa.Column('run_count', sa.Integer(), server_default='0'),
            sa.Column('success_count', sa.Integer(), server_default='0'),
            sa.Column('error_count', sa.Integer(), server_default='0'),
            sa.Column('created_at', sa.DateTime()),
            sa.Column('updated_at', sa.DateTime()),
            sa.ForeignKeyConstraint(['project_id'], ['project.id'], ),
        )

    # 添加 task_instance 的 spider_id 字段（幂等）
    columns = {c['name'] for c in inspector.get_columns('task_instance')}
    if 'spider_id' not in columns:
        op.add_column('task_instance', sa.Column('spider_id', sa.BigInteger(), nullable=True))
        op.create_foreign_key('fk_task_instance_spider', 'task_instance', 'spider', ['spider_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_task_instance_spider', 'task_instance', type_='foreignkey')
    op.drop_column('task_instance', 'spider_id')
    op.drop_table('spider')
