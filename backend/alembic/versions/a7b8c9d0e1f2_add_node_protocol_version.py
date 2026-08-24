"""add protocol_version to node (A7)

Revision ID: a7b8c9d0e1f2
Revises: c1r2a3w4l5o
Create Date: 2026-08-24 18:00:00.000000

节点表新增 protocol_version 列，Agent 注册时上报协议版本号；
控制面据此判定 agent 版本是否兼容（agent_compatible），
低于 REQUIRED_PROTOCOL_VERSION 时前端可标黄提示重新部署。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'c1r2a3w4l5o'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 存在性检查（幂等，避免重复迁移报错）
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "mysql":
        res = bind.execute(
            sa.text("SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='node' "
                    "AND COLUMN_NAME='protocol_version'")).scalar()
        if res > 0:
            return
    op.add_column('node', sa.Column('protocol_version', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('node', 'protocol_version')
