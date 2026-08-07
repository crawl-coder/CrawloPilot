import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path


def _resolve_env_file() -> Optional[str]:
    """
    解析 .env 文件路径，按优先级：
    1. CRAWLOPILOT_ENV_FILE 环境变量显式指定
    2. 仓库根目录 .env（本地开发：backend/app/core/config.py 上溯 4 级）
    3. 当前工作目录 .env（其他部署形态）

    都找不到则返回 None：仅使用系统环境变量（如 Docker Compose 的 environment: 注入）。

    注意（优先级语义）：本地开发时 .env 通过 load_dotenv(override=True) **覆盖**
    系统环境变量（防止 shell 旧变量干扰，见底部加载逻辑）；无 .env 时（如 Docker
    容器）系统环境变量自然生效。
    """
    candidates = [
        os.environ.get("CRAWLOPILOT_ENV_FILE"),
        Path(__file__).parent.parent.parent.parent / ".env",
        Path.cwd() / ".env",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


class Settings(BaseSettings):
    # App
    APP_NAME: str = "CrawloPilot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_TYPE: str = "mysql"  # mysql 或 sqlite
    SQLITE_PATH: str = "./crawlopilot.db"
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "crawlopilot"
    MYSQL_PASSWORD: str = "crawlopilot123"
    MYSQL_DATABASE: str = "crawlopilot"
    
    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_TYPE == "sqlite":
            import os
            db_path = self.SQLITE_PATH
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', db_path)
            return f"sqlite:///{os.path.abspath(db_path)}"
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
    
    # 安全密钥
    # 兼容旧配置：仅设置 SECRET_KEY 时，JWT 与凭据加密共用（回退）。
    # 生产建议显式设置 JWT_SECRET_KEY / CREDENTIAL_ENCRYPTION_KEY 实现密钥分离。
    SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_SECRET_KEY: Optional[str] = None   # 未设置时回退 SECRET_KEY
    CREDENTIAL_ENCRYPTION_KEY: Optional[str] = None  # 未设置时回退 SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    @property
    def jwt_secret(self) -> str:
        """JWT 签名密钥：优先 JWT_SECRET_KEY，回退 SECRET_KEY"""
        return self.JWT_SECRET_KEY or self.SECRET_KEY

    @property
    def credential_secret(self) -> str:
        """凭据加密密钥：优先 CREDENTIAL_ENCRYPTION_KEY，回退 SECRET_KEY"""
        return self.CREDENTIAL_ENCRYPTION_KEY or self.SECRET_KEY

    def validate_secrets(self) -> None:
        """启动时校验安全密钥：生产环境不得使用源码默认值"""
        default = "your-secret-key-change-in-production"
        if self.DEBUG:
            return
        if self.jwt_secret == default or self.credential_secret == default:
            raise RuntimeError(
                "检测到安全密钥仍为默认值，拒绝启动。生产环境必须设置 "
                "JWT_SECRET_KEY（JWT 签名）与 CREDENTIAL_ENCRYPTION_KEY（凭据加密），"
                "生成方式：openssl rand -hex 32"
            )

    # 开放注册：False 时 /auth/register 仅 admin 可用（内部平台建议关闭）
    ALLOW_OPEN_REGISTER: bool = False
    
    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET_NAME: str = "crawlopilot"
    MINIO_SECURE: bool = False
    
    # Docker
    DOCKER_HOST: str = "unix:///var/run/docker.sock"

    # 上传/代码/日志根目录
    # 默认相对路径 "uploads"（本地开发 = backend/uploads，Docker = /app/uploads 挂载卷）
    # 生产环境务必配置绝对路径，如 /data/crawlopilot/uploads
    UPLOAD_DIR: str = "uploads"

    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8080"]
    
    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


# .env 优先于系统环境变量（override=True）：本地开发防止 shell 旧变量干扰；
# Docker 容器内无 .env 文件时此逻辑天然跳过，由 compose environment: 注入生效
_ENV_FILE = _resolve_env_file()
if _ENV_FILE:
    from dotenv import load_dotenv
    load_dotenv(_ENV_FILE, override=True)

settings = Settings()

# 生产环境安全校验（DEBUG=False 时拒绝默认密钥）
settings.validate_secrets()
