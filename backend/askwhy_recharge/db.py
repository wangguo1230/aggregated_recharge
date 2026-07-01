"""AskWhy 服务的 SQLAlchemy 数据库基础设施（独立引擎，与充值中心隔离）。"""

from __future__ import annotations

from collections.abc import Iterator
import threading

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import load_askwhy_settings


class Base(DeclarativeBase):
    pass


_engine = None
_engine_url = ""
_engine_lock = threading.RLock()
SessionLocal = sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)


def configure_database(database_url: str) -> None:
    global _engine, _engine_url
    selected_url = str(database_url or "").strip()
    if not selected_url:
        raise RuntimeError("数据库连接不能为空")
    if not selected_url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        raise RuntimeError("AskWhy 服务只支持 PostgreSQL 数据库")
    with _engine_lock:
        if _engine is not None and _engine_url == selected_url:
            return
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(selected_url, pool_pre_ping=True, future=True)
        _engine_url = selected_url
        SessionLocal.configure(bind=_engine)


def _ensure_engine_current() -> None:
    configure_database(load_askwhy_settings().database_url)


def get_engine():
    _ensure_engine_current()
    return _engine


def init_askwhy_db() -> None:
    from . import models  # noqa: F401

    _ensure_engine_current()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _apply_schema_patches(engine)


def _apply_schema_patches(engine) -> None:
    """补齐早期库缺失的向后兼容列（无 Alembic，仅做新增列）。"""

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "askwhy_orders" in tables:
            columns = {c["name"] for c in inspector.get_columns("askwhy_orders")}
            if "external_code" not in columns:
                connection.execute(text("ALTER TABLE askwhy_orders ADD COLUMN external_code VARCHAR(64) DEFAULT ''"))
                connection.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_askwhy_orders_external_code ON askwhy_orders (external_code)")
                )

        # gpt_batches 后加入的列（给已存在的表补列）。
        if "gpt_batches" in tables:
            columns = {c["name"] for c in inspector.get_columns("gpt_batches")}
            patches = {
                "paused_reason": "ALTER TABLE gpt_batches ADD COLUMN paused_reason VARCHAR(255) DEFAULT ''",
                "concurrency": "ALTER TABLE gpt_batches ADD COLUMN concurrency INTEGER DEFAULT 1",
                "channel": "ALTER TABLE gpt_batches ADD COLUMN channel VARCHAR(20) DEFAULT 'gpt86'",
            }
            for column, ddl in patches.items():
                if column not in columns:
                    connection.execute(text(ddl))

        # gpt_orders 后加入的列。
        if "gpt_orders" in tables:
            order_columns = {c["name"] for c in inspector.get_columns("gpt_orders")}
            if "channel" not in order_columns:
                connection.execute(text("ALTER TABLE gpt_orders ADD COLUMN channel VARCHAR(20) DEFAULT 'gpt86'"))

        # gpt_batch_items 后加入的列。
        if "gpt_batch_items" in tables:
            item_columns = {c["name"] for c in inspector.get_columns("gpt_batch_items")}
            if "stock_retries" not in item_columns:
                connection.execute(text("ALTER TABLE gpt_batch_items ADD COLUMN stock_retries INTEGER DEFAULT 0"))
            if "channel" not in item_columns:
                connection.execute(text("ALTER TABLE gpt_batch_items ADD COLUMN channel VARCHAR(20) DEFAULT 'gpt86'"))
            if "built_session_encrypted" not in item_columns:
                connection.execute(text("ALTER TABLE gpt_batch_items ADD COLUMN built_session_encrypted TEXT DEFAULT ''"))


def get_db_session() -> Iterator[Session]:
    _ensure_engine_current()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
