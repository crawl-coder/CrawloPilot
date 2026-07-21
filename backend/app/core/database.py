import logging
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
    connect_args={
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
    },
    echo=settings.DEBUG,
)


@event.listens_for(engine, "connect")
def set_connect_timeout(dbapi_connection, connection_record):
    """设置连接超时"""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET SESSION wait_timeout = 3600")
        cursor.execute("SET SESSION interactive_timeout = 3600")
        cursor.execute("SET SESSION net_read_timeout = 30")
        cursor.execute("SET SESSION net_write_timeout = 30")
        cursor.close()
    except Exception:
        pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """获取数据库会话（FastAPI依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    except OperationalError as e:
        logger.error(f"Database operational error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
