from app.core.database import Base
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Enum, Boolean, ForeignKey, JSON, DECIMAL, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import enum


class User(Base):
    __tablename__ = "user"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    full_name = Column(String(128))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    teams = relationship("TeamMember", back_populates="user")
    roles = relationship("Role", secondary="user_role", back_populates="users")


class Team(Base):
    __tablename__ = "team"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    members = relationship("TeamMember", back_populates="team")
    projects = relationship("Project", back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_member"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("user.id"), nullable=False)
    team_id = Column(BigInteger, ForeignKey("team.id"), nullable=False)
    role = Column(String(32), default="member")  # admin/member
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="teams")
    team = relationship("Team", back_populates="members")


class Role(Base):
    __tablename__ = "role"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    users = relationship("User", secondary="user_role", back_populates="roles")
    permissions = relationship("Permission", secondary="role_permission")


class UserRole(Base):
    __tablename__ = "user_role"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("user.id"), nullable=False)
    role_id = Column(BigInteger, ForeignKey("role.id"), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permission"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    role_id = Column(BigInteger, ForeignKey("role.id"), nullable=False)
    permission_id = Column(BigInteger, ForeignKey("permission.id"), nullable=False)


class Permission(Base):
    __tablename__ = "permission"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text)


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class Project(Base):
    __tablename__ = "project"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    team_id = Column(BigInteger, ForeignKey("team.id"), nullable=False)
    description = Column(Text)
    git_url = Column(String(512))
    status = Column(Enum(ProjectStatus), default=ProjectStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    team = relationship("Team", back_populates="projects")
    versions = relationship("ProjectVersion", back_populates="project")
    schedules = relationship("Schedule", back_populates="project")
    spiders = relationship("Spider", back_populates="project")


class ProjectVersionStatus(str, enum.Enum):
    BUILDING = "building"
    READY = "ready"
    DEPLOYED = "deployed"


class ProjectVersion(Base):
    __tablename__ = "project_version"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    version = Column(String(32), nullable=False, index=True)
    package_url = Column(String(512))
    config_snapshot = Column(JSON)
    image_tag = Column(String(128))
    status = Column(Enum(ProjectVersionStatus), default=ProjectVersionStatus.BUILDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="versions")


class SpiderType(str, enum.Enum):
    CRAWLO = "crawlo"              # Crawlo 框架(主打)
    SCRAPY = "scrapy"              # Scrapy 框架
    SELENIUM = "selenium"          # Selenium
    PLAYWRIGHT = "playwright"      # Playwright
    REQUESTS = "requests"          # Requests
    CUSTOM = "custom"              # 自定义


class SpiderStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class Spider(Base):
    __tablename__ = "spider"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    description = Column(Text)
    spider_type = Column(Enum(SpiderType, values_callable=lambda e: [x.value for x in e]), default=SpiderType.SCRAPY)
    status = Column(Enum(SpiderStatus), default=SpiderStatus.DRAFT)
    
    # Git相关
    git_url = Column(String(512))  # Git仓库地址
    git_auth_type = Column(String(32), default="password")  # password 或 ssh
    git_username = Column(String(128))  # Git用户名
    git_password = Column(String(256))  # Git密码/Token
    git_ssh_key = Column(Text)  # SSH私钥
    git_passphrase = Column(String(256))  # SSH私钥密码
    git_branch = Column(String(128), default="main")  # 分支
    
    # 代码相关
    code_path = Column(String(512))  # 代码目录路径
    entry_file = Column(String(256))  # 入口文件 (如 run.py)
    spider_name = Column(String(128))  # 爬虫名称 (用于 crawlo run)
    
    # 配置
    config = Column(JSON)  # 爬虫配置
    schedule_config = Column(JSON)  # 调度配置
    
    # 统计
    last_run_at = Column(DateTime)
    last_run_status = Column(String(32))
    run_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="spiders")
    task_instances = relationship("TaskInstance", back_populates="spider")


class ScheduleType(str, enum.Enum):
    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"
    DEPENDENCY = "dependency"


class Schedule(Base):
    __tablename__ = "schedule"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    spider_name = Column(String(128), nullable=False)
    node_id = Column(BigInteger, ForeignKey("node.id"), nullable=True)
    schedule_type = Column(Enum(ScheduleType), nullable=False)
    cron_expr = Column(String(64))
    interval_seconds = Column(Integer)
    priority = Column(Integer, default=5)
    max_concurrency = Column(Integer, default=1)
    timeout_seconds = Column(Integer, default=3600)
    retry_strategy = Column(JSON)
    enabled = Column(Boolean, default=True)
    next_run_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="schedules")
    node = relationship("Node")
    task_instances = relationship("TaskInstance", back_populates="schedule")


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"  # 暂停状态
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"  # 手动取消


class TaskInstance(Base):
    __tablename__ = "task_instance"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    schedule_id = Column(BigInteger, ForeignKey("schedule.id"), nullable=True)
    spider_id = Column(BigInteger, ForeignKey("spider.id"), nullable=True)
    node_id = Column(BigInteger, ForeignKey("node.id"), nullable=True)  # 部署目标节点
    spider_name = Column(String(128), nullable=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    worker_node = Column(String(64))
    container_id = Column(String(64))
    process_id = Column(Integer)  # 本地进程 PID (非Docker模式)
    deploy_mode = Column(String(16), default="local")  # local / docker / ssh
    workspace = Column(String(512))  # SSH模式服务器工作目录
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration = Column(DECIMAL(10, 2))  # 运行时长(秒)
    stats = Column(JSON)
    log_url = Column(String(512))
    error_message = Column(Text)  # 错误信息
    pages_crawled = Column(Integer, default=0)  # 爬取页面数
    items_scraped = Column(Integer, default=0)  # 采集条目数
    errors_count = Column(Integer, default=0)  # 错误数量
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    schedule = relationship("Schedule", back_populates="task_instances")
    spider = relationship("Spider", back_populates="task_instances")
    node = relationship("Node", back_populates="task_instances")


class EnvironmentConfig(Base):
    __tablename__ = "environment_config"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    env_name = Column(String(32), nullable=False)  # dev/test/prod
    config = Column(JSON)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ==================== Phase 2: 部署引擎 ====================

class DeployStatus(str, enum.Enum):
    PENDING = "pending"
    BUILDING = "building"
    DEPLOYING = "deploying"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class DeployStrategy(str, enum.Enum):
    BLUE_GREEN = "blue_green"  # 蓝绿部署
    ROLLING = "rolling"        # 滚动更新
    RECREATE = "recreate"      # 重新创建


class Deploy(Base):
    __tablename__ = "deploy"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    version_id = Column(BigInteger, ForeignKey("project_version.id"), nullable=False)
    strategy = Column(Enum(DeployStrategy), nullable=False, default=DeployStrategy.RECREATE)
    status = Column(Enum(DeployStatus), default=DeployStatus.PENDING)
    target_env = Column(String(32), default="production")  # production/staging
    node_id = Column(BigInteger, ForeignKey("node.id"))
    container_ids = Column(JSON)  # 存储容器 ID 列表
    error_message = Column(Text)
    deployed_by = Column(BigInteger, ForeignKey("user.id"))
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project = relationship("Project")
    version = relationship("ProjectVersion")
    node = relationship("Node")
    deployer = relationship("User")


class NodeStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DRAINING = "draining"  # 正在排空
    MAINTENANCE = "maintenance"


class ServerStatus(str, enum.Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class Server(Base):
    """真实服务器（宿主机）"""

    __tablename__ = "server"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    host = Column(String(256), nullable=False)
    os_type = Column(String(64))
    os_version = Column(String(128))
    cpu_cores = Column(Integer, default=0)
    memory_total = Column(BigInteger, default=0)
    disk_total = Column(BigInteger, default=0)
    region = Column(String(64))
    labels = Column(JSON)
    description = Column(String(512))
    status = Column(Enum(ServerStatus), default=ServerStatus.UNKNOWN)
    last_probed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    nodes = relationship("Node", back_populates="server")


class Node(Base):
    __tablename__ = "node"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    host = Column(String(256), nullable=False)
    port = Column(Integer, default=2375)  # Docker API 端口 / SSH 端口
    connect_type = Column(String(16), default="docker")  # ssh / agent / docker
    ssh_host = Column(String(256))      # SSH 连接地址（与 host 解耦）
    ssh_port = Column(Integer, default=22)  # SSH 端口
    ssh_user = Column(String(64), default="root")  # SSH 用户
    ssh_pwd = Column(String(512))       # SSH 密码
    ssh_key = Column(Text)              # SSH 私钥
    docker_host = Column(String(256))  # Docker socket 路径
    status = Column(Enum(NodeStatus), default=NodeStatus.OFFLINE)
    labels = Column(JSON)  # 节点标签
    resources = Column(JSON)  # CPU、内存、磁盘信息
    os_type = Column(String(64))        # Linux / Windows / macOS
    os_version = Column(String(128))    # Ubuntu 22.04 LTS
    cpu_cores = Column(Integer, default=0)  # CPU 核数
    memory_total = Column(BigInteger, default=0)  # 总内存 (bytes)
    disk_total = Column(BigInteger, default=0)   # 总磁盘 (bytes)
    cpu_usage = Column(DECIMAL(5,2), default=0.00)    # CPU 使用率 %
    memory_usage = Column(DECIMAL(5,2), default=0.00) # 内存使用率 %
    disk_usage = Column(DECIMAL(5,2), default=0.00)   # 磁盘使用率 %
    agent_version = Column(String(32))  # Agent 版本号
    agent_status = Column(String(16), default="offline")  # agent 状态
    agent_token = Column(String(64), nullable=True, index=True)  # Agent 注册令牌
    server_id = Column(BigInteger, ForeignKey("server.id"), nullable=True, index=True)
    public_ip = Column(String(64))      # 公网 IP
    private_ip = Column(String(64))     # 内网 IP
    container_count = Column(Integer, default=0)
    last_heartbeat = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    server = relationship("Server", back_populates="nodes")
    containers = relationship("Container", back_populates="node")
    deploys = relationship("Deploy", back_populates="node")
    task_instances = relationship("TaskInstance", back_populates="node")


class ContainerStatus(str, enum.Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    EXITED = "exited"
    DEAD = "dead"


class Container(Base):
    __tablename__ = "container"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    container_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(256), nullable=False, index=True)
    node_id = Column(BigInteger, ForeignKey("node.id"), nullable=False)
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    version_id = Column(BigInteger, ForeignKey("project_version.id"))
    image = Column(String(256), nullable=False)
    status = Column(Enum(ContainerStatus), default=ContainerStatus.CREATED)
    ports = Column(JSON)  # 端口映射
    environment = Column(JSON)  # 环境变量
    resource_limits = Column(JSON)  # 资源限制
    health_check = Column(JSON)  # 健康检查配置
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    stopped_at = Column(DateTime)
    
    # Relationships
    node = relationship("Node", back_populates="containers")
    project = relationship("Project")
    version = relationship("ProjectVersion")
