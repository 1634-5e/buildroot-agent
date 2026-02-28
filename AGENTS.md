# AGENTS.md

Guidelines for agentic coding assistants working on this buildroot-agent repository.

## Project Overview

```
/root/Projects/buildroot-agent/
├── buildroot-agent/     # C Agent (嵌入式设备端)
│   ├── include/         # Headers (agent.h)
│   ├── src/             # Sources (agent_*.c)
│   └── scripts/         # Build scripts
├── buildroot-server/    # Python Server (中央服务器)
│   ├── config/          # Settings (settings.py)
│   ├── handlers/        # Message handlers
│   ├── protocol/        # Message types, codec
│   └── server/          # WebSocket/Socket servers
└── PROTOCOL.md          # 通信协议规范
```

**Runtime:** buildroot2015.08.1, gcc 4.9, cmake 2.8.12.2, openssl 1.1.1

---

## Build Commands

### C/CMake (buildroot-agent)
```bash
cd buildroot-agent && mkdir -p build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Release -DSTATIC_LINK=ON
make                                                    # Output: bin/buildroot-agent

./scripts/build.sh                                    # 本地编译 (x86_64)
./scripts/build.sh --cross                            # 交叉编译 (arm)
./scripts/release.sh                                  # 发布构建+打包
rm -rf build                                          # 清理
```

**Note:** cmake 2.8.12 不支持 `-B` 参数，需使用 `mkdir -p build && cd build && cmake ..` 方式

**Options:** `-DCMAKE_BUILD_TYPE=Debug`, `-DSTATIC_LINK=ON`, `-DCMAKE_TOOLCHAIN_FILE=cmake/arm-buildroot.cmake`

### Python (buildroot-server)

**项目管理工具:** [uv](https://docs.astral.sh/uv/) - 现代 Python 包管理器

```bash
cd buildroot-server

# 安装依赖
uv sync                                              # 同步依赖（根据 pyproject.toml）
uv add <package>                                     # 添加新依赖
uv remove <package>                                  # 移除依赖

# 运行服务器
uv run python main.py                                # 使用 uv 运行（自动激活虚拟环境）

# 代码检查与格式化
uv run ruff check . && uv run ruff format .          # 检查+格式化
uv run mypy .                                        # 类型检查（如需要）

# 其他常用命令
uv lock                                              # 更新 uv.lock
uv pip list                                          # 查看已安装包
uv venv                                              # 创建虚拟环境（如需要）
```

**依赖管理说明:**
- 使用 `pyproject.toml` 声明依赖（dependencies 和 optional-dependencies）
- `uv.lock` 锁定精确版本，确保可复现的构建
- 无需手动管理 requirements.txt

### Web (buildroot-web)
前端 Web 控制台，已从单文件 HTML 重构为多文件结构：
- `index.html` - 主页面
- `js/app.js`, `js/websocket.js`, `js/terminal.js`, `js/utils.js`, `js/config.js` - JavaScript 模块
- `css/style.css` - 样式文件
- `public/` - 静态资源（xterm.js, Ace Editor, 字体等）

---

## Testing

**Status:** No automated tests exist. When adding:
```bash
# Python: pytest with pytest-asyncio
pytest -v                                            # Run all
pytest tests/test_handler.py -k "test_name"         # Single test

# C: add -DBUILD_TESTS=ON to cmake
ctest --test-dir build
```

---

## C Code Style (buildroot-agent)

| Type | Style | Example |
|------|-------|---------|
| Types/Structs | `snake_case_t` | `agent_context_t` |
| Enum/Macros | `UPPER_CASE` | `MSG_TYPE_HEARTBEAT` |
| Functions | `snake_case()` | `agent_init()` |
| Globals | `g_prefix_` | `g_agent_ctx` |

**Headers:** `include/agent.h` | **Sources:** `src/agent_*.c`

```c
LOG_DEBUG("调试: %d", value);
LOG_ERROR("错误: %s", strerror(errno));
// Return: 0=success, -1=error
// Memory: calloc() + free(), check NULL
// Thread safety: pthread_mutex_t for shared data
```

---

## Python Code Style (buildroot-server)

```python
# Import order: stdlib → third-party → local
import logging
from typing import Optional
from pydantic import BaseModel, Field
from config.settings import settings
```

| Type | Style | Example |
|------|-------|---------|
| Classes | `PascalCase` | `CloudServer` |
| Functions/Variables | `snake_case` | `handle_connection` |
| Constants | `UPPER_CASE` | `MESSAGE_HEADER_SIZE` |
| Private | `_prefix` | `_get_remote_address()` |

```python
# Type annotations
name: str | None = None
def get_device(self, device_id: str) -> dict[str, Any] | None: ...

# Logging
logger = logging.getLogger(__name__)
logger.info(f"设备连接: {device_id}")
```

---

## Protocol Sync

Message types in two places, must stay synchronized:
- C: `buildroot-agent/include/agent.h` (`msg_type_t` enum)
- Python: `buildroot-server/protocol/constants.py` (`MessageType` IntEnum)

Key types: `HEARTBEAT=0x01`, `PTY_CREATE=0x10`, `FILE_REQUEST=0x20`, `CMD_REQUEST=0x30`, `REGISTER=0xF0`

---

## Key Notes

- **Dual Protocol:** WebSocket (8765) for Web, TCP Socket (8766) for Agent
- **Config:** YAML `config.yaml` + env vars with `BR_SERVER_` prefix
- **File Transfer:** Chunked, max 64KB, Base64 encoding
- **Update Flow:** Non-mandatory needs Web approval; mandatory auto-proceeds
- **Database:** 
  - SQLite: 自动建表（开发/测试环境）
  - PostgreSQL/MySQL: 需手动建表或使用 schema.sql（生产环境）