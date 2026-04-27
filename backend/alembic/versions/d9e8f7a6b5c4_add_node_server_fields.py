"""add node server management fields

Revision ID: d9e8f7a6b5c4
Revises: c1d2e3f4a5b6
Create Date: 2026-04-27 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'd9e8f7a6b5c4'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 节点管理增强字段
    op.add_column('node', sa.Column('connect_type', sa.String(16), server_default='docker'))
    op.add_column('node', sa.Column('ssh_host', sa.String(256), nullable=True))
    op.add_column('node', sa.Column('ssh_port', sa.Integer(), server_default='22'))
    op.add_column('node', sa.Column('ssh_user', sa.String(64), server_default='root'))
    op.add_column('node', sa.Column('os_type', sa.String(64), nullable=True))
    op.add_column('node', sa.Column('os_version', sa.String(128), nullable=True))
    op.add_column('node', sa.Column('cpu_cores', sa.Integer(), server_default='0'))
    op.add_column('node', sa.Column('memory_total', sa.BigInteger(), server_default='0'))
    op.add_column('node', sa.Column('disk_total', sa.BigInteger(), server_default='0'))
    op.add_column('node', sa.Column('cpu_usage', sa.DECIMAL(5, 2), server_default='0.00'))
    op.add_column('node', sa.Column('memory_usage', sa.DECIMAL(5, 2), server_default='0.00'))
    op.add_column('node', sa.Column('disk_usage', sa.DECIMAL(5, 2), server_default='0.00'))
    op.add_column('node', sa.Column('agent_version', sa.String(32), nullable=True))
    op.add_column('node', sa.Column('agent_status', sa.String(16), server_default='offline'))
    op.add_column('node', sa.Column('public_ip', sa.String(64), nullable=True))
    op.add_column('node', sa.Column('private_ip', sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column('node', 'private_ip')
    op.drop_column('node', 'public_ip')
    op.drop_column('node', 'agent_status')
    op.drop_column('node', 'agent_version')
    op.drop_column('node', 'disk_usage')
    op.drop_column('node', 'memory_usage')
    op.drop_column('node', 'cpu_usage')
    op.drop_column('node', 'disk_total')
    op.drop_column('node', 'memory_total')
    op.drop_column('node', 'cpu_cores')
    op.drop_column('node', 'os_version')
    op.drop_column('node', 'os_type')
    op.drop_column('node', 'ssh_user')
    op.drop_column('node', 'ssh_port')
    op.drop_column('node', 'ssh_host')
    op.drop_column('node', 'connect_type')
