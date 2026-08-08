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
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())
    cols = {c['name'] for c in inspector.get_columns('schedule')}
    if 'node_id' not in cols:
        op.add_column('schedule', sa.Column('node_id', sa.BigInteger(), nullable=True))
    dialect = op.get_bind().dialect.name.lower()
    try:
        if dialect.startswith('sqlite'):
            with op.batch_alter_table('schedule') as batch_op:
                batch_op.create_foreign_key('fk_schedule_node_id', 'node', ['node_id'], ['id'])
        else:
            op.create_foreign_key('fk_schedule_node_id', 'schedule', 'node', ['node_id'], ['id'])
    except NotImplementedError:
        import logging as _log
        _log.getLogger(__name__).warning(
            '跳过 schedule.node_id FK 创建（SQLite 不支持 ALTER ADD CONSTRAINT）',
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name.lower()
    try:
        if dialect.startswith('sqlite'):
            with op.batch_alter_table('schedule') as batch_op:
                batch_op.drop_constraint('fk_schedule_node_id', type_='foreignkey')
        else:
            op.drop_constraint('fk_schedule_node_id', 'schedule', type_='foreignkey')
    except Exception:
        pass
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())
    cols = {c['name'] for c in inspector.get_columns('schedule')}
    if 'node_id' in cols:
        op.drop_column('schedule', 'node_id')
