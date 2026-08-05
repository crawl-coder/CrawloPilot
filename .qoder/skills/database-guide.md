# CrawloPilot 数据库开发指南

## 数据库配置

### 连接信息
- 主机: 117.72.16.51
- 端口: 3306
- 用户: crawlo
- 数据库: crawlo_pilot

### 配置文件
- `.env` - 环境变量
- `backend/app/core/config.py` - 配置类
- `backend/app/core/database.py` - 数据库连接

## 数据模型

### 核心模型

#### 1. 用户相关
- `User` - 用户表
- `Team` - 团队表
- `TeamMember` - 团队成员
- `Role` - 角色表
- `Permission` - 权限表
- `UserRole` - 用户角色关联
- `RolePermission` - 角色权限关联

#### 2. 项目相关
- `Project` - 项目表
- `ProjectVersion` - 项目版本表

#### 3. 部署相关 (Phase 2)
- `Deploy` - 部署记录表
- `Node` - 节点表
- `Container` - 容器表

#### 4. 调度相关
- `Schedule` - 调度配置表
- `TaskInstance` - 任务实例表（关键字段需掌握）
  - `id` - 主键
  - `spider_id` - 关联爬虫
  - `status` - ENUM: PENDING/RUNNING/PAUSED/SUCCESS/FAILED/TIMEOUT/CANCELLED
  - `started_at` / `finished_at` - 起止时间
  - `duration` - 执行时长（秒）
  - `process_id` - 本地进程 PID
  - `pages_crawled` / `items_scraped` / `errors_count` - 爬虫指标
  - `error_message` - 错误信息

#### 5. 其他
- `AlertRule` - 告警规则
- `ProxyPool` - 代理池
- `ApiConfig` - API 配置
- `AuditLog` - 审计日志
- `EnvironmentConfig` - 环境配置

## Alembic 迁移管理

### 基本操作

#### 1. 创建迁移
```bash
cd backend
alembic revision --autogenerate -m "描述性信息"
```

#### 2. 执行迁移
```bash
alembic upgrade head
```

#### 3. 回滚迁移
```bash
# 回滚一个版本
alembic downgrade -1

# 回滚到特定版本
alembic downgrade <revision_id>
```

#### 4. 查看迁移历史
```bash
alembic history
alembic current
```

### 创建新模型示例

#### 1. 定义模型
```python
# backend/app/models/__init__.py

class YourModel(Base):
    __tablename__ = "your_model"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    related = relationship("RelatedModel", back_populates="your_model")
```

#### 2. 生成迁移
```bash
alembic revision --autogenerate -m "add your_model table"
```

#### 3. 检查迁移文件
```python
# alembic/versions/xxx_add_your_model_table.py

def upgrade():
    op.create_table(
        'your_model',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_your_model_name'), 'your_model', ['name'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_your_model_name'), table_name='your_model')
    op.drop_table('your_model')
```

#### 4. 执行迁移
```bash
alembic upgrade head
```

## 数据库查询示例

### 基本查询
```python
from app.core.database import SessionLocal
from app.models import YourModel

db = SessionLocal()
try:
    # 查询单个
    item = db.query(YourModel).get(item_id)
    
    # 条件查询
    items = db.query(YourModel).filter(
        YourModel.name.like("%keyword%")
    ).all()
    
    # 分页查询
    items = db.query(YourModel)\
              .order_by(YourModel.created_at.desc())\
              .limit(20)\
              .offset(0)\
              .all()
    
    # 计数
    count = db.query(YourModel).filter(
        YourModel.status == "active"
    ).count()
    
    # 关联查询
    items = db.query(YourModel)\
              .join(RelatedModel)\
              .filter(RelatedModel.status == "active")\
              .all()
finally:
    db.close()
```

### 在 API 中使用
```python
@router.get("/items")
async def list_items(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    items = db.query(YourModel)\
              .order_by(YourModel.created_at.desc())\
              .limit(limit)\
              .offset(offset)\
              .all()
    return items
```

## Pydantic Schema 定义

### 基本 Schema
```python
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class YourModelBase(BaseModel):
    name: str
    description: Optional[str] = None

class YourModelCreate(YourModelBase):
    pass

class YourModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class YourModelResponse(YourModelBase):
    id: int
    created_at: Any
    updated_at: Optional[Any]
    
    class Config:
        from_attributes = True
```

## 数据库初始化

### 开发环境初始化
```bash
cd backend
python init_db.py
```

这会创建：
- 默认管理员账号 (admin/admin123)
- 默认团队
- 角色和权限系统

## 数据库调试

### 使用 DBeaver
1. 连接信息:
   - Host: 117.72.16.51
   - Port: 3306
   - Database: crawlo_pilot
   - User: crawlo
   - Password: bJjGTZN4cDf6bmjc

### 常用查询
```sql
-- 查看所有表
SHOW TABLES;

-- 查看表结构
DESCRIBE your_table;

-- 查看数据
SELECT * FROM your_table ORDER BY created_at DESC LIMIT 10;

-- 查看迁移历史
SELECT * FROM alembic_version;

-- 查看用户
SELECT id, username, email, is_active FROM user;

-- 查看部署记录
SELECT id, project_id, strategy, status, created_at FROM deploy ORDER BY created_at DESC LIMIT 10;
```

## 最佳实践

### 1. 命名规范
- 表名: 小写，下划线分隔 (your_model)
- 字段名: 小写，下划线分隔 (created_at)
- 模型类名: 大驼峰 (YourModel)

### 2. 索引
- 外键自动创建索引
- 频繁查询的字段添加索引
- 使用 `index=True` 参数

### 3. 关系定义
```python
# 一对多
class Parent(Base):
    children = relationship("Child", back_populates="parent")

class Child(Base):
    parent_id = Column(BigInteger, ForeignKey("parent.id"))
    parent = relationship("Parent", back_populates="children")

# 多对多 (使用关联表)
user_roles = Table('user_role', Base.metadata,
    Column('user_id', BigInteger, ForeignKey('user.id')),
    Column('role_id', BigInteger, ForeignKey('role.id'))
)
```

### 4. 时间字段
```python
from datetime import datetime

created_at = Column(DateTime, default=datetime.utcnow)
updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 5. 枚举类型
```python
import enum

class StatusEnum(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

status = Column(Enum(StatusEnum), default=StatusEnum.ACTIVE)
```

## 数据备份

### 导出数据库
```bash
mysqldump -h 117.72.16.51 -u crawlo -p crawlo_pilot > backup.sql
```

### 导入数据库
```bash
mysql -h 117.72.16.51 -u crawlo -p crawlo_pilot < backup.sql
```

---

## ⚠️ MySQL ENUM 列管理（易踩坑）

### 问题描述
当 Python 模型中 ENUM 新增枚举值后，MySQL 数据库中的 ENUM 列不会自动跟随更新，写入新值时会报：
```
DataError: (1265, "Data truncated for column 'status' at row 1")
```

### 根因
- SQLAlchemy 的 `alembic revision --autogenerate` **无法检测** ENUM 值的增减
- 手动 ALTER TABLE 是唯一可靠的解决方案

### 修复方法
```sql
-- 查看当前 ENUM 定义
SHOW COLUMNS FROM task_instance WHERE Field = 'status';

-- 重新定义完整 ENUM 列表（必须包含所有旧值 + 新值）
ALTER TABLE task_instance MODIFY COLUMN status 
  ENUM('PENDING','RUNNING','PAUSED','SUCCESS','FAILED','TIMEOUT','CANCELLED') 
  DEFAULT 'PENDING';
```

### 使用 Python 执行修复
```python
# 在需要添加新值的服务中
from sqlalchemy import text
db.execute(text("""
    ALTER TABLE task_instance MODIFY COLUMN status 
    ENUM('PENDING','RUNNING','PAUSED','SUCCESS','FAILED','TIMEOUT','CANCELLED') 
    DEFAULT 'PENDING'
"""))
db.commit()
```

### 最佳实践
1. **任何时候**给 ENUM 列加新值，都必须使用 **ALTER TABLE 完整重定义**
2. Python 模型、Pydantic Schema、MySQL 列定义三者必须同步
3. 建议在 Alembic 迁移文件中手动编写 `op.execute("ALTER TABLE ...")` 来管理 ENUM 变更
