import asyncio
import logging

from server.cloud_server import CloudServer
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

    await start_batch_buffers()

    server = CloudServer()
    try:
        await server.run()
    except KeyboardInterrupt:
        print("\n服务器已停止")
    finally:
        await stop_batch_buffers()
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
