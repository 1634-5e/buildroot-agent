#!/usr/bin/env python3
"""
Buildroot Agent Server - SQLModel Database Manager
使用SQLModel ORM管理数据库连接，支持多种数据库（PostgreSQL、MySQL、SQLite等）
"""

import logging
import re
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlmodel import SQLModel

from config.settings import settings

logger = logging.getLogger(__name__)


def patched_get_server_version_info(self, connection):
    v = connection.exec_driver_sql("SELECT version()").scalar()
    m = re.search(r"AtlasDB (\d+)\.(\d+)\.(\d+)(?:\.(\d+))?", v)
    if m:
        return tuple(int(x) for x in m.groups() if x is not None)

    logger.warning("Falling back to PostgreSQL version 12 for AtlasDB")
    return (12, 0)


PGDialect._get_server_version_info = patched_get_server_version_info


class DatabaseManager:
    """数据库管理器 - 单例模式"""

    _instance = None
    _engine = None
    _async_session_maker = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(
        self,
        database_url: str = None,
        pool_size: int = None,
        max_overflow: int = None,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
    ) -> None:
        """初始化数据库连接"""
        if self._engine is not None:
            logger.warning("Database already initialized")
            return

        if database_url is None:
            database_url = self._build_database_url()

        if pool_size is None:
            pool_size = settings.db_pool_min
        if max_overflow is None:
            max_overflow = settings.db_pool_max - settings.db_pool_min

        logger.info(
            f"Initializing database: {database_url.split('@')[-1]} "
            f"(pool_size={pool_size}, max_overflow={max_overflow})"
        )

        self._engine = create_async_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,
            echo=settings.log_level == "DEBUG",
        )

        self._async_session_maker = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        await self._test_connection()
        logger.info("Database initialized successfully")

    def _build_database_url(self) -> str:
        """根据配置构建数据库URL"""
        db_type = getattr(settings, "db_type", "postgresql").lower()

        if db_type == "sqlite":
            db_name = settings.db_name
            return f"sqlite+aiosqlite:///{db_name}.db"

        elif db_type == "mysql":
            encoded_password = quote_plus(settings.db_password)
            return f"mysql+aiomysql://{settings.db_user}:{encoded_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"

        else:
            logger.info("Using PostgreSQL database driver")
            encoded_password = quote_plus(settings.db_password)
            return f"postgresql+asyncpg://{settings.db_user}:{encoded_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"

    async def _test_connection(self):
        """测试数据库连接"""
        async with self.get_session() as session:
            await session.execute(select(func.now()))
            logger.debug("Database test query succeeded")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取会话上下文管理器（调用者需要手动commit）"""
        if self._async_session_maker is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        async with self._async_session_maker() as session:
            yield session

    async def close(self):
        """关闭数据库连接"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._async_session_maker = None
            logger.info("Database connection closed")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._engine is not None

    async def create_tables(self):
        """创建所有表 - 仅在 SQLite 时自动创建，其他数据库需手动执行迁移"""
        if self._engine is None:
            raise RuntimeError("Database not initialized")

        # 检查是否为 SQLite
        db_url = str(self._engine.url)
        if not db_url.startswith("sqlite"):
            logger.info(
                "Skipping auto table creation for non-SQLite database (PostgreSQL/MySQL)"
            )
            logger.info("Please run database migrations manually or use schema.sql")
            return

        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
            logger.info("Database tables created (SQLite)")

    async def drop_tables(self):
        """删除所有表 - 仅在 SQLite 时允许"""
        if self._engine is None:
            raise RuntimeError("Database not initialized")

        # 安全检查：只允许删除 SQLite 表
        db_url = str(self._engine.url)
        if not db_url.startswith("sqlite"):
            logger.error("Drop tables is only allowed for SQLite (safety check)")
            raise RuntimeError("Cannot drop tables for non-SQLite database")

        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
            logger.info("Database tables dropped (SQLite)")


# 全局数据库管理器实例
db_manager = DatabaseManager()


async def get_db_session():
    """获取数据库会话（用于依赖注入）"""
    return db_manager.get_session().__aenter__()


async def get_sync_db_session():
    """获取同步数据库会话（用于快速操作）"""
    return db_manager.get_session()
