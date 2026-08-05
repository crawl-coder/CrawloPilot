"""add node agent token field

Revision ID: a1b2c3d4e5f6
Revises: 5bd99488bb24
Create Date: 2026-08-06 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '5bd99488bb24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('node', sa.Column('agent_token', sa.String(64), nullable=True))
    op.create_index('ix_node_agent_token', 'node', ['agent_token'])


def downgrade() -> None:
    op.drop_index('ix_node_agent_token', table_name='node')
    op.drop_column('node', 'agent_token')
