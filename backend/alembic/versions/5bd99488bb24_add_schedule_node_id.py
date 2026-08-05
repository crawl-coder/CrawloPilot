"""add_schedule_node_id

Revision ID: 5bd99488bb24
Revises: c4aabb19606c
Create Date: 2026-04-27 15:06:38.977056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bd99488bb24'
down_revision: Union[str, None] = 'c4aabb19606c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('schedule', sa.Column('node_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key('fk_schedule_node_id', 'schedule', 'node', ['node_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_schedule_node_id', 'schedule', type_='foreignkey')
    op.drop_column('schedule', 'node_id')
