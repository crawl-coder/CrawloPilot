"""add git credentials (user personal + shared pool)

Revision ID: g1c2r3e4d5s6
Revises: s1e2r3v4e5r6
Create Date: 2026-08-07 10:00:00.000000

- user.git_credentials: 个人 Git 凭据（Fernet 加密 JSON）
- git_credential 表: 共享 Git 凭据（团队机器人凭据，敏感字段加密）
- spider.git_credential_id: 引用共享凭据
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'g1c2r3e4d5s6'
down_revision: Union[str, None] = 's1e2r3v4e5r6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('git_credentials', sa.Text(), nullable=True))

    op.create_table(
        'git_credential',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.String(512), nullable=True),
        sa.Column('auth_type', sa.String(32), nullable=False, server_default='password'),
        sa.Column('username', sa.String(128), nullable=True),
        sa.Column('password', sa.Text(), nullable=True),
        sa.Column('ssh_key', sa.Text(), nullable=True),
        sa.Column('passphrase', sa.Text(), nullable=True),
        sa.Column('default_branch', sa.String(128), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1')),
        sa.Column('created_by', sa.BigInteger(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_git_credential_name', 'git_credential', ['name'], unique=True)

    op.add_column('spider', sa.Column('git_credential_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        'fk_spider_git_credential', 'spider', 'git_credential',
        ['git_credential_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_spider_git_credential', 'spider', type_='foreignkey')
    op.drop_column('spider', 'git_credential_id')
    op.drop_index('ix_git_credential_name', table_name='git_credential')
    op.drop_table('git_credential')
    op.drop_column('user', 'git_credentials')
