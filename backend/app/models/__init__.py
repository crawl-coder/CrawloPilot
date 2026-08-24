from app.core.database import Base
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Enum, Boolean, ForeignKey, JSON, DECIMAL, Integer, UniqueConstraint, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.time_utils import cn_now
import enum


class User(Base):
    __tablename__ = "user"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=True, index=True)  # 邮箱可选
    password_hash = Column(String(256), nullable=False)
    full_name = Column(String(128))
    is_active = Column(Boolean, default=True)
    # 个人 Git 凭据（Fernet 加密的 JSON：auth_type/username/password/ssh_key/passphrase/default_branch）
    git_credentials = Column(Text)
    created_at = Column(DateTime, default=cn_now)
    updated_at = Column(DateTime, default=cn_now, onupdate=cn_now)
    
    # Relationships
    teams = relationship("TeamMember", back_populates="user")
    roles = relationship("Role", secondary="user_role", back_populates="users")


class LoginLog(Base):
    """登录日志：记录用户、IP、时间与结果"""

    __tablename__ = "login_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=True, index=True)
    username = Column(String(64), nullable=False, index=True)
    ip = Column(String(64))
    user_agent = Column(String(256))
    success = Column(Boolean, default=True)
    detail = Column(String(128))  # 失败原因（成功为空）
    login_at = Column(DateTime, default=cn_now, index=True)


class Team(Base):
    __tablename__ = "team"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=cn_now)
    updated_at = Column(DateTime, default=cn_now, onupdate=cn_now)
    
    # Relationships
    members = relationship("TeamMember", back_populates="team")
    projects = relationship("Project", back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_member"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("user.id"), nullable=False)
    team_id = Column(BigInteger, ForeignKey("team.id"), nullable=False)
    role = Column(String(32), default="member")  # admin/member
    joined_at = Column(DateTime, default=cn_now)
    
    # Relationships
    user = relationship("User", back_populates="teams")
    team = relationship("Team", back_populates="members")


class Role(Base):
    __tablename__ = "role"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=cn_now)
    
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
    created_at = Column(DateTime, default=cn_now)
    updated_at = Column(DateTime, default=cn_now, onupdate=cn_now)
    
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
    created_at = Column(DateTime, default=cn_now)
    
    # Relationships
    project = relationship("Project", back_populates="versions")


class GitCredential(Base):
    """共享 Git 凭据（团队机器人账号 / Deploy Key），由管理员维护，创建爬虫时引用"""
    __tablename__ = "git_credential"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    description = Column(String(512))
    auth_type = Column(String(32), nullable=False, default="password")  # password 或 ssh
    username = Column(String(128))           # Git 用户名（明文，用于展示/拼装 URL）
    password = Column(Text)                  # Git 密码/Token（Fernet 加密）
    ssh_key = Column(Text)                   # SSH 私钥（Fernet 加密）
    passphrase = Column(Text)                # SSH 私钥密码（Fernet 加密）
    default_branch = Column(String(128))     # 默认分支（可选，仅作创建时建议值）
    is_active = Column(Boolean, default=True)
    created_by = Column(BigInteger, ForeignKey("user.id"))
    created_at = Column(DateTime, default=cn_now)
    updated_at = Column(DateTime, default=cn_now, onupdate=cn_now)

    # Relationships
    creator = relationship("User")


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
    # 引用的共享 Git 凭据（团队机器人凭据）；设置后 git ops 优先使用凭据池中的凭据
    git_credential_id = Column(BigInteger, ForeignKey("git_credential.id"), nullable=True)
    
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
    
    created_at = Column(DateTime, default=cn_now)
    updated_at = Column(DateTime, default=cn_now, onupdate=cn_now)
    
    # Relationships
    project = relationship("Project", back_populates="spiders")
    task_instances = relationship("TaskInstance", back_populates="spider")
    git_credential = relationship("GitCredential")


class ScheduleType(str, enum.Enum):
    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"
    DEPENDENCY = "dependency"


class Schedule(Base):
    __tablename__ = "schedule"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128))  # 调度名称（可空，默认"爬虫名-周期"）
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    spider_id = Column(BigInteger, ForeignKey("spider.id"), nullable=True)  # 存量未匹配行可能为 NULL（已禁用）
    spider_name = Column(String(128), nullable=False)
    node_id = Column(BigInteger, ForeignKey("node.id"), nullable=True)
    schedule_type = Column(Enum(ScheduleType), nullable=False)
    cron_expr = Column(String(64))
    interval_seconds = Column(Integer)
    run_at = Column(DateTime)  # once 触发时间
    timezone = Column(String(64), default="Asia/Shanghai")
    priority = Column(Integer, default=5)
    max_concurrency = Column(Integer, default=1)
    timeout_seconds = Column(Integer, default=3600)
    retry_strategy = Column(JSON)
    enabled = Column(Boolean, default=True)
    next_run_time = Column(DateTime)
    last_run_at = Column(DateTime)
    last_run_status = Column(String(32))
    last_run_task_id = Column(BigInteger)
    run_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    description = Column(Text)
    created_by = Column(BigInteger, ForeignKey("user.id"))
    created_at = Column(DateTime, default=cn_now)
    updated_at = Column(DateTime, default=cn_now, onupdate=cn_now)
    
    # Relationships
    project = relationship("Project", back_populates="schedules")
    spider = relationship("Spider")
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


class DeployMode(str, enum.Enum):
    """任务部署模式：控制面将爬虫代码发送到何处执行。"""
    LOCAL = "local"
    SSH = "ssh"
    DOCKER = "docker"
    AGENT = "agent"

    @classmethod
    def from_connect_type(cls, connect_type: str | None) -> "DeployMode":
        """根据 Node.connect_type 映射到默认 DeployMode。"""
        mapping = {"docker": cls.DOCKER, "ssh": cls.SSH, "agent": cls.AGENT}
        if connect_type and connect_type in mapping:
            return mapping[connect_type]
        return cls.LOCAL


class TaskInstance(Base):
    __tablename__ = "task_instance"
    __table_args__ = (
        # 调度触发幂等：同一调度同一期望触发时间最多一个任务
        UniqueConstraint("schedule_id", "expected_run_at", name="uq_schedule_expected_run"),
    )
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    schedule_id = Column(BigInteger, ForeignKey("schedule.id"), nullable=True)
    spider_id = Column(BigInteger, ForeignKey("spider.id"), nullable=True)
    node_id = Column(BigInteger, ForeignKey("node.id"), nullable=True)  # 部署目标节点
    spider_name = Column(String(128), nullable=True)
    expected_run_at = Column(DateTime)  # 期望触发时间（调度幂等用）
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    worker_node = Column(String(64))
    container_id = Column(String(64))
    process_id = Column(Integer)  # 本地进程 PID (非Docker模式)
    deploy_mode = Column(Enum(DeployMode), default=DeployMode.LOCAL)  # local / ssh / docker / agent
    memory_limit = Column(String(16), nullable=True)  # Docker 内存限制，如 "512m" / "1g"
    cpu_limit = Column(Float, nullable=True)  # Docker CPU 配额（核数）
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
    created_at = Column(DateTime, default=cn_now)
    
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
    created_at = Column(DateTime, default=cn_now)
    updated_at = Column(DateTime, default=cn_now, onupdate=cn_now)


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
    created_at = Column(DateTime, default=cn_now)
    
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
    created_at = Column(DateTime, default=cn_now)
    updated_at = Column(DateTime, default=cn_now, onupdate=cn_now)

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
    protocol_version = Column(Integer, default=0)  # Agent 协议版本号（递增整数）
    agent_status = Column(String(16), default="offline")  # agent 状态
    agent_token = Column(String(64), nullable=True, index=True)  # Agent 注册令牌
    server_id = Column(BigInteger, ForeignKey("server.id"), nullable=True, index=True)
    public_ip = Column(String(64))      # 公网 IP
    private_ip = Column(String(64))     # 内网 IP
    container_count = Column(Integer, default=0)
    last_heartbeat = Column(DateTime)
    created_at = Column(DateTime, default=cn_now)
    updated_at = Column(DateTime, default=cn_now, onupdate=cn_now)
    
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
    created_at = Column(DateTime, default=cn_now)
    started_at = Column(DateTime)
    stopped_at = Column(DateTime)
    
    # Relationships
    node = relationship("Node", back_populates="containers")
    project = relationship("Project")
    version = relationship("ProjectVersion")
