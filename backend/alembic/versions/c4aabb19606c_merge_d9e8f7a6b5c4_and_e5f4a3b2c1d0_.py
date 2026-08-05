"""merge d9e8f7a6b5c4 and e5f4a3b2c1d0 heads

Revision ID: c4aabb19606c
Revises: d9e8f7a6b5c4, e5f4a3b2c1d0
Create Date: 2026-04-27 12:33:01.789183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4aabb19606c'
down_revision: Union[str, None] = ('d9e8f7a6b5c4', 'e5f4a3b2c1d0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
