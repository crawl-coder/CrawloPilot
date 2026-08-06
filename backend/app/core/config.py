from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    # App
    APP_NAME: str = "CrawloPilot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_TYPE: str = "mysql"  # mysql 或 sqlite
    SQLITE_PATH: str = "./crawlopilot.db"
    MYSQL_HOST: str = "mysql"
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
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
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

    # Celery
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    
    @property
    def CELERY_BROKER_URL_PROP(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL
    
    @property
    def CELERY_RESULT_BACKEND_PROP(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8080"]
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        # 禁用系统环境变量，只使用 .env 文件
        extra="ignore"
    )


# 手动加载 .env 文件以确保优先级
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

settings = Settings()
