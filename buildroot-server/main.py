import asyncio
import logging
import uvicorn

from server.cloud_server import CloudServer
from server.http_server import app as http_app
from config.settings import settings

from database.db_manager import db_manager
from database.batch_buffer import start_batch_buffers, stop_batch_buffers

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await db_manager.initialize()

    # 创建数据库表（仅 SQLite）
    try:
        await db_manager.create_tables()
    except Exception as e:
        # 忽略表已存在的错误
        if "already exists" not in str(e):
            logger.warning(f"Error creating tables: {e}")

    await start_batch_buffers()

    # WebSocket 服务器
    ws_server = CloudServer()

    # HTTP 服务器配置
    http_config = uvicorn.Config(
        http_app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
    http_server = uvicorn.Server(http_config)

    logger.info("启动双服务器模式：")
    logger.info("  - WebSocket 服务器: ws://0.0.0.0:8765")
    logger.info("  - HTTP API 服务器: http://0.0.0.0:8000")

    try:
        # 并行运行两个服务器
        await asyncio.gather(
            ws_server.run(),
            http_server.serve(),
        )
    except KeyboardInterrupt:
        print("\n服务器已停止")
    finally:
        await stop_batch_buffers()
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
