"""add audit_log table (E1)

Revision ID: e1f2g3h4i5j6
Revises: d4e5f6g7h8i9
Create Date: 2026-08-25 00:00:00.000000

操作审计：记录所有写操作（POST/PUT/DELETE），用于团队协作追溯。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e1f2g3h4i5j6'
down_revision: Union[str, None] = 'd4e5f6g7h8i9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        res = bind.execute(sa.text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='audit_log'")).scalar()
        if res > 0:
            return
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.BigInteger, nullable=True),
        sa.Column('username', sa.String(128)),
        sa.Column('action', sa.String(32), nullable=False),
        sa.Column('resource_type', sa.String(32)),
        sa.Column('resource_id', sa.String(64)),
        sa.Column('resource_name', sa.String(256)),
        sa.Column('method', sa.String(8)),
        sa.Column('path', sa.String(512)),
        sa.Column('ip', sa.String(64)),
        sa.Column('user_agent', sa.String(256)),
        sa.Column('detail', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('audit_log')
