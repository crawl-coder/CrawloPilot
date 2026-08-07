"""user.email nullable (email optional at registration)

Revision ID: u3s4e5r6m7a8
Revises: s2c3h4e5d6u7
Create Date: 2026-08-07 16:00:00.000000

注册邮箱改为可选：user.email 放宽为可空。
唯一索引保留——MySQL 唯一索引允许多个 NULL，无冲突。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'u3s4e5r6m7a8'
down_revision: Union[str, None] = 's2c3h4e5d6u7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'user', 'email',
        existing_type=sa.String(128),
        nullable=True,
    )


def downgrade() -> None:
    # 回填空邮箱为占位值后再收紧（避免 NOT NULL 迁移失败）
    op.execute("UPDATE user SET email = CONCAT('user_', id, '@placeholder.local') WHERE email IS NULL")
    op.alter_column(
        'user', 'email',
        existing_type=sa.String(128),
        nullable=False,
    )
