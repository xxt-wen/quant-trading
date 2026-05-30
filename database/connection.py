"""
SQLAlchemy 数据库连接管理
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
import config

# SQLite + WAL 模式，支持读写并发
engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    echo=False,  # 生产环境关闭 SQL 日志
    connect_args={"check_same_thread": False},  # SQLite 多线程支持
)

# 启用 WAL 模式
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_session():
    """获取数据库会话"""
    return SessionLocal()


def init_db():
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """删除所有表（危险操作，仅开发用）"""
    Base.metadata.drop_all(bind=engine)
