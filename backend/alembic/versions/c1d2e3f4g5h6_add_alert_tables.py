"""add alert tables (Wave C)

Revision ID: c1d2e3f4g5h6
Revises: b3d4e5f6g7h8
Create Date: 2026-08-24 22:00:00.000000

新增三张告警表：
- alert_rule：规则定义（类型、阈值、窗口、冷却期、启用状态）
- alert_record：告警记录（触发事件、目标、消息、确认状态）
- alert_channel：通知通道（钉钉/企微/飞书/自定义 Webhook）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c1d2e3f4g5h6'
down_revision: Union[str, None] = 'b3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    def _table_exists(name):
        if dialect == "mysql":
            return bind.execute(sa.text(
                f"SELECT COUNT(*) FROM information_schema.TABLES "
                f"WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{name}'")).scalar() > 0
        return False

    if not _table_exists('alert_rule'):
        op.create_table(
            'alert_rule',
            sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('rule_type', sa.Enum('task_failed', 'task_timeout', 'consecutive_failures',
                                           'success_rate', 'node_offline', 'zombie_converged',
                                           name='alertruletype'), nullable=False),
            sa.Column('spider_id', sa.BigInteger, sa.ForeignKey('spider.id'), nullable=True),
            sa.Column('project_id', sa.BigInteger, sa.ForeignKey('project.id'), nullable=True),
            sa.Column('threshold', sa.Integer, server_default='1'),
            sa.Column('window_minutes', sa.Integer, server_default='60'),
            sa.Column('cooldown_minutes', sa.Integer, server_default='30'),
            sa.Column('severity', sa.Enum('info', 'warning', 'critical',
                                          name='alertseverity'), server_default='warning'),
            sa.Column('enabled', sa.Boolean, server_default='1'),
            sa.Column('created_by', sa.BigInteger, sa.ForeignKey('user.id'), nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        )

    if not _table_exists('alert_record'):
        op.create_table(
            'alert_record',
            sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column('rule_id', sa.BigInteger, sa.ForeignKey('alert_rule.id'), nullable=False),
            sa.Column('event_type', sa.String(32), nullable=False),
            sa.Column('target_id', sa.BigInteger, nullable=True),
            sa.Column('target_name', sa.String(128), nullable=True),
            sa.Column('message', sa.Text, nullable=False),
            sa.Column('severity', sa.Enum('info', 'warning', 'critical',
                                          name='alertseverity'), server_default='warning'),
            sa.Column('acknowledged', sa.Boolean, server_default='0'),
            sa.Column('acknowledged_by', sa.BigInteger, sa.ForeignKey('user.id'), nullable=True),
            sa.Column('acknowledged_at', sa.DateTime, nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        )

    if not _table_exists('alert_channel'):
        op.create_table(
            'alert_channel',
            sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column('name', sa.String(128), nullable=False),
            sa.Column('channel_type', sa.Enum('dingtalk', 'wechat', 'feishu', 'custom',
                                              name='alertchanneltype'), nullable=False),
            sa.Column('webhook_url', sa.String(512), nullable=False),
            sa.Column('enabled', sa.Boolean, server_default='1'),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table('alert_channel')
    op.drop_table('alert_record')
    op.drop_table('alert_rule')
    op.execute("DROP TYPE IF EXISTS alertchanneltype")
    op.execute("DROP TYPE IF EXISTS alertseverity")
    op.execute("DROP TYPE IF EXISTS alertruletype")
