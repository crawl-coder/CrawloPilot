"""deploy_mode 从 String 改为 Enum，并记录迁移图谱（迁移历史清理方案：文档化而非删除）

Revision ID: z9x8c7v6b5n4
Revises: c1r2a3w4l5o
Create Date: 2026-08-07

迁移图谱（HEAD = z9x8c7v6b5n4）：
  55e9d375362c init_all_tables  ← 根
       └── 7c6c3df56972 add_phase2_deploy_engine_tables
            ├── b6985578c953 add_spider_table           ← 分支 1（幂等：has_table 检查）
            │    └── e5f4a3b2c1d0 add_task_instance_deploy_fields
            └── 4a8c26e16402 create_spider_table        ← 分支 2（幂等：has_table 检查）
                 └── c1d2e3f4a5b6 add_task_instance_fields
                      └── d9e8f7a6b5c4 add_node_server_fields
                           └── c4aabb19606c merge (合并 d9e8 与 e5f4 两支)
                                └── 5bd99488bb24 add_schedule_node_id
                                     └── a1b2c3d4e5f6 add_node_agent_token
                                          └── s1e2r3v4e5r6 add_server_table
                                               └── g1c2r3e4d5s6 add_git_credentials
                                                    └── s2c3h4e5d6u7 unify_schedule_migration
                                                         └── u3s4e5r6m7a8 user_email_nullable
                                                              └── c1r2a3w4l5o add_task_resources
                                                                   └── z9x8c7v6b5n4 deploy_mode_enum (当前)
说明：
  - b698 / 4a8c 为早期并行分支，两边均以 `IF NOT EXISTS` 幂等方式建 spider 表，
    不会产生"表已存在"冲突；在后续 c4aabb 合并节点之前各自独立演化。
  - 历史迁移文件 **不删除**，保证已应用迁移的生产库 schema 链路完整；
    新库从空库执行 `alembic upgrade head` 会按拓扑顺序经过上述幂等保护。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'z9x8c7v6b5n4'
down_revision: Union[str, None] = 'c1r2a3w4l5o'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 合法枚举值（与 app/models/__init__.py 中 DeployMode 保持一致）
_DEPLOY_ENUM_NAME = 'deploymode'
_DEPLOY_VALUES = ('local', 'ssh', 'docker', 'agent')


def _is_mysql(bind) -> bool:
    return bind.dialect.name.lower() in ('mysql', 'pymysql', 'mariadb')


def upgrade() -> None:
    """String(16) -> Enum(local|ssh|docker|agent)。
    
    MySQL 上走两步：先加约束/改列类型；SQLite 用 batch_alter_table。
    不依赖 Enum 原生，MySQL 用 VARCHAR + CHECK 即可（SQLAlchemy Enum 在 MySQL
    上会建独立 ENUM 类型，跨库迁移麻烦）。
    """
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('task_instance')}
    if 'deploy_mode' not in cols:
        # 老库可能缺列（虽然几乎不可能），补上
        op.add_column('task_instance', sa.Column('deploy_mode', sa.String(16), default='local'))

    if _is_mysql(bind):
        # 收紧长度 + CHECK，保持 VARCHAR 形式避免 MySQL 重建表 + enum 类型管理麻烦
        op.execute(
            "ALTER TABLE task_instance "
            "MODIFY COLUMN deploy_mode VARCHAR(16) NOT NULL DEFAULT 'local',"
            f"ADD CONSTRAINT ck_task_instance_deploy_mode CHECK (deploy_mode IN {tuple(_DEPLOY_VALUES)})"
        )
    else:
        # SQLite / PostgreSQL：SQLite 用 batch_alter_table，PostgreSQL 原生 Enum
        dialect = bind.dialect.name.lower()
        if dialect.startswith('postgres'):
            # 只在 PostgreSQL 上建原生 ENUM 类型
            enum_type = sa.Enum(*_DEPLOY_VALUES, name=_DEPLOY_ENUM_NAME)
            enum_type.create(bind, checkfirst=True)
            op.alter_column(
                'task_instance', 'deploy_mode',
                type_=enum_type,
                existing_type=sa.String(16),
                existing_nullable=True,
                server_default='local',
                nullable=False,
                postgresql_using=f"deploy_mode::{_DEPLOY_ENUM_NAME}",
            )
        else:
            # SQLite: 长度没意义，但 CHECK 依然有效
            with op.batch_alter_table('task_instance') as batch_op:
                batch_op.alter_column(
                    'deploy_mode',
                    existing_type=sa.String(16),
                    type_=sa.String(16),
                    existing_nullable=True,
                    server_default='local',
                    nullable=False,
                )
                batch_op.create_check_constraint(
                    'ck_task_instance_deploy_mode',
                    sa.text(
                        "deploy_mode IN ('local','ssh','docker','agent')"
                    ),
                )

    # 处理历史脏数据（若旧数据里有非标准字符串）：把非法值归一到 'local'
    op.execute(
        "UPDATE task_instance SET deploy_mode = 'local' "
        f"WHERE deploy_mode NOT IN {tuple(_DEPLOY_VALUES)}"
    )


def downgrade() -> None:
    """回退：去掉 CHECK 约束，列改回 VARCHAR(16)，允许为 NULL。"""
    bind = op.get_bind()

    if _is_mysql(bind):
        op.execute(
            "ALTER TABLE task_instance "
            "DROP CHECK ck_task_instance_deploy_mode,"
            "MODIFY COLUMN deploy_mode VARCHAR(16)"
        )
    else:
        dialect = bind.dialect.name.lower()
        if dialect.startswith('postgres'):
            op.alter_column(
                'task_instance', 'deploy_mode',
                type_=sa.String(16),
                existing_type=sa.Enum(*_DEPLOY_VALUES, name=_DEPLOY_ENUM_NAME),
                existing_server_default='local',
                server_default=None,
                nullable=True,
            )
            enum_type = sa.Enum(*_DEPLOY_VALUES, name=_DEPLOY_ENUM_NAME)
            enum_type.drop(bind, checkfirst=True)
        else:
            with op.batch_alter_table('task_instance') as batch_op:
                batch_op.drop_constraint('ck_task_instance_deploy_mode', type_='check')
                batch_op.alter_column(
                    'deploy_mode',
                    existing_type=sa.String(16),
                    type_=sa.String(16),
                    existing_nullable=False,
                    nullable=True,
                    server_default=None,
                )
