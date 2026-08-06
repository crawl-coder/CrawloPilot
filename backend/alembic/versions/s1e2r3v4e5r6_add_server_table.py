"""add server table and node server_id

Revision ID: s1e2r3v4e5r6
Revises: a1b2c3d4e5f6
Create Date: 2026-08-06 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 's1e2r3v4e5r6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'server',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('host', sa.String(256), nullable=False),
        sa.Column('os_type', sa.String(64), nullable=True),
        sa.Column('os_version', sa.String(128), nullable=True),
        sa.Column('cpu_cores', sa.Integer(), server_default='0'),
        sa.Column('memory_total', sa.BigInteger(), server_default='0'),
        sa.Column('disk_total', sa.BigInteger(), server_default='0'),
        sa.Column('region', sa.String(64), nullable=True),
        sa.Column('labels', sa.JSON(), nullable=True),
        sa.Column('description', sa.String(512), nullable=True),
        sa.Column('status', sa.String(16), server_default='unknown'),
        sa.Column('last_probed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_server_name', 'server', ['name'], unique=True)
    op.add_column('node', sa.Column('server_id', sa.BigInteger(), nullable=True))
    op.create_index('ix_node_server_id', 'node', ['server_id'])


def downgrade() -> None:
    op.drop_index('ix_node_server_id', table_name='node')
    op.drop_column('node', 'server_id')
    op.drop_index('ix_server_name', table_name='server')
    op.drop_table('server')
