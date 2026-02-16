from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Dict, Optional
from pathlib import Path


class Settings(BaseSettings):
    """服务器配置"""

    ws_port: int = Field(default=8765, description="WebSocket端口")
    socket_port: int = Field(default=8766, description="Socket端口")
    host: str = Field(default="0.0.0.0", description="监听地址")

    ping_interval: int = Field(default=30, description="心跳间隔(秒)")
    ping_timeout: int = Field(default=10, description="心跳超时(秒)")
    session_timeout: int = Field(default=300, description="会话超时(秒)")

    upload_dir: str = Field(default="./uploads", description="上传目录")
    updates_dir: str = Field(default="./updates", description="更新包目录")
    latest_yaml: str = Field(
        default="./updates/latest.yml", description="最新版本 YAML 文件路径"
    )

    chunk_sizes: Dict[str, int] = {
        "small": 8 * 1024,
        "medium": 32 * 1024,
        "large": 64 * 1024,
        "xlarge": 128 * 1024,
    }
    max_retries: int = 5
    retry_delay_base: float = 1.0

    log_level: str = Field(default="DEBUG", description="日志级别")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = "BR_SERVER_"


settings = Settings()
