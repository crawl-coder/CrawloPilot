"""add task_instance deploy fields and node SSH auth fields

Revision ID: e5f4a3b2c1d0
Revises: b6985578c953
Create Date: 2026-04-27 12:00:00.000000

"""
from typing import Sequence, Union
import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = 'e5f4a3b2c1d0'
down_revision: Union[str, None] = 'b6985578c953'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === task_instance 新增字段（带 IF NOT EXISTS 保护） ===
    _add_column_if_not_exists('task_instance', 'node_id', sa.BigInteger(), nullable=True)
    _add_column_if_not_exists('task_instance', 'deploy_mode', sa.String(16), server_default='local')
    _add_column_if_not_exists('task_instance', 'workspace', sa.String(512), nullable=True)
    
    # 外键（如果不存在）
    try:
        op.create_foreign_key('fk_task_instance_node', 'task_instance', 'node', ['node_id'], ['id'])
    except Exception:
        pass

    # === node 新增 SSH 认证字段 ===
    _add_column_if_not_exists('node', 'ssh_pwd', sa.String(512), nullable=True)
    _add_column_if_not_exists('node', 'ssh_key', sa.Text(), nullable=True)


def _add_column_if_not_exists(table, column, type, **kwargs):
    """安全添加列（忽略已存在的错误）"""
    try:
        op.add_column(table, sa.Column(column, type, **kwargs))
        logger.info(f"列 {table}.{column} 已添加")
    except Exception as e:
        if "Duplicate column" in str(e) or "already exists" in str(e):
            logger.info(f"列 {table}.{column} 已存在，跳过")
        else:
            raise


def downgrade() -> None:
    # === node 回滚 ===
    op.drop_column('node', 'ssh_key')
    op.drop_column('node', 'ssh_pwd')
    
    # === task_instance 回滚 ===
    op.drop_constraint('fk_task_instance_node', 'task_instance', type_='foreignkey')
    op.drop_column('task_instance', 'workspace')
    op.drop_column('task_instance', 'deploy_mode')
    op.drop_column('task_instance', 'node_id')
