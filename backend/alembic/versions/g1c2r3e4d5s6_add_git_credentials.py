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
    # user.git_credentials: IF NOT EXISTS 保护（SQLite ALTER ADD COLUMN 本身不支持 IF NOT EXISTS，
    # 通过 inspect 先判断；render_as_batch=True 下 ADD 仍然要求列不存在，否则会报 duplicate）
    from sqlalchemy import inspect
    insp = inspect(op.get_bind())
    user_cols = {c['name'] for c in insp.get_columns('user')}
    if 'git_credentials' not in user_cols:
        op.add_column('user', sa.Column('git_credentials', sa.Text(), nullable=True))

    if not insp.has_table('git_credential'):
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
            # 注意：render_as_batch + SQLite batch 模式下 create_foreign_key 必须显式命名，
            # 且 sa.ForeignKey(...) 隐式创建的匿名 FK 在 batch flush 时会报 "Constraint must have a name"。
            # 因此改为显式 ForeignKeyConstraint(name=...) 命名。
            sa.Column('created_by', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.ForeignKeyConstraint(['created_by'], ['user.id'], name='fk_git_credential_created_by'),
        )
    # 幂等：索引不存在才创建
    from sqlalchemy.exc import OperationalError
    try:
        existing_idx = {i['name'] for i in insp.get_indexes('git_credential')}
        if 'ix_git_credential_name' not in existing_idx:
            op.create_index('ix_git_credential_name', 'git_credential', ['name'], unique=True)
    except Exception:
        pass

    # spider.git_credential_id + FK
    spider_cols = {c['name'] for c in insp.get_columns('spider')} if insp.has_table('spider') else set()
    if 'git_credential_id' not in spider_cols:
        op.add_column('spider', sa.Column('git_credential_id', sa.BigInteger(), nullable=True))
    # render_as_batch=True 下 SQLite 需要显式 FK 名；MySQL/PG 也保持显式命名。
    try:
        existing_fks = {fk['name'] for fk in insp.get_foreign_keys('spider')}
    except Exception:
        existing_fks = set()
    if 'fk_spider_git_credential' not in existing_fks:
        try:
            op.create_foreign_key(
                'fk_spider_git_credential', 'spider', 'git_credential',
                ['git_credential_id'], ['id'],
            )
        except Exception:
            import logging as _log
            _log.getLogger(__name__).warning('跳过 fk_spider_git_credential 创建（可能 dialect 不支持或已存在）')


def downgrade() -> None:
    from sqlalchemy import inspect
    insp = inspect(op.get_bind())
    try:
        existing_fks = {fk['name'] for fk in insp.get_foreign_keys('spider')}
    except Exception:
        existing_fks = set()
    if 'fk_spider_git_credential' in existing_fks:
        try:
            op.drop_constraint('fk_spider_git_credential', 'spider', type_='foreignkey')
        except Exception:
            pass
    spider_cols = {c['name'] for c in insp.get_columns('spider')}
    if 'git_credential_id' in spider_cols:
        op.drop_column('spider', 'git_credential_id')
    try:
        existing_idx = {i['name'] for i in insp.get_indexes('git_credential')}
        if 'ix_git_credential_name' in existing_idx:
            op.drop_index('ix_git_credential_name', table_name='git_credential')
    except Exception:
        pass
    if insp.has_table('git_credential'):
        op.drop_table('git_credential')
    user_cols = {c['name'] for c in insp.get_columns('user')}
    if 'git_credentials' in user_cols:
        op.drop_column('user', 'git_credentials')
