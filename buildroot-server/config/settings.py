import os
import logging
from pathlib import Path
from typing import Dict, Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

logger = logging.getLogger(__name__)


def load_yaml_config(config_path: str | None = None) -> Dict[str, Any]:
    search_paths = []
    if config_path:
        search_paths.append(config_path)
    search_paths.append(os.environ.get("BR_SERVER_CONFIG", "config.yaml"))
    project_root = Path(__file__).parent.parent
    search_paths.append(str(project_root / "config.yaml"))

    for path_str in search_paths:
        path = Path(path_str)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {path}")
                return config or {}

    logger.warning(f"Config file not found in: {search_paths}, using defaults")
    return {}


_yaml_config = load_yaml_config()


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
        default="./updates/latest.yml", description="最新版本YAML路径"
    )

    chunk_sizes: Dict[str, int] = {
        "small": 8 * 1024,
        "medium": 32 * 1024,
        "large": 64 * 1024,
        "xlarge": 128 * 1024,
    }
    max_retries: int = 5
    retry_delay_base: float = 1.0

    db_type: str = Field(default="postgresql", description="数据库类型")
    db_host: str = Field(default="localhost", description="数据库主机")
    db_port: int = Field(default=5432, description="数据库端口")
    db_user: str = Field(default="buildroot", description="数据库用户")
    db_password: str = Field(default="buildroot", description="数据库密码")
    db_name: str = Field(default="buildroot_agent", description="数据库名称")
    db_pool_min: int = Field(default=5, description="数据库连接池最小大小")
    db_pool_max: int = Field(default=20, description="数据库连接池最大大小")
    db_query_timeout: int = Field(default=30, description="数据库查询超时(秒)")
    db_statement_timeout: int = Field(default=60, description="数据库语句超时(秒)")

    log_level: str = Field(default="INFO", description="日志级别")

    @field_validator("chunk_sizes", mode="before")
    @classmethod
    def load_chunk_sizes(cls, v):
        return v or {
            "small": 8 * 1024,
            "medium": 32 * 1024,
            "large": 64 * 1024,
            "xlarge": 128 * 1024,
        }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BR_SERVER_",
        extra="allow",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.apply_yaml_config()

    def apply_yaml_config(self):
        """Apply YAML config as fallback values"""
        env_prefix = "BR_SERVER_"

        # Server config
        server_config = _yaml_config.get("server", {})
        for key, value in server_config.items():
            env_key = f"{env_prefix}{key.upper()}"
            if env_key not in os.environ:
                setattr(self, key, value)

        # File transfer config
        file_transfer_config = _yaml_config.get("file_transfer", {})
        if file_transfer_config:
            if "chunk_sizes" in file_transfer_config:
                self.chunk_sizes = file_transfer_config["chunk_sizes"]
            if "max_retries" in file_transfer_config:
                self.max_retries = file_transfer_config["max_retries"]
            if "retry_delay_base" in file_transfer_config:
                self.retry_delay_base = file_transfer_config["retry_delay_base"]

        # Database config
        database_config = _yaml_config.get("database", {})
        for key, value in database_config.items():
            env_key = f"{env_prefix}{key.upper()}"
            if env_key not in os.environ:
                setattr(self, key, value)

        # Logging config
        logging_config = _yaml_config.get("logging", {})
        if "log_level" in logging_config:
            env_key = f"{env_prefix}LOG_LEVEL"
            if env_key not in os.environ:
                setattr(self, key, value)


settings = Settings()
