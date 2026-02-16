import asyncio
import logging

from server.cloud_server import CloudServer
from config.settings import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def main() -> None:
    server = CloudServer()
    try:
        await server.run()
    except KeyboardInterrupt:
        print("\n服务器已停止")


if __name__ == "__main__":
    asyncio.run(main())
