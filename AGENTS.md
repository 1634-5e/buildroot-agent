# AGENTS.md

Guidelines for agentic coding assistants working on this buildroot-agent repository.

## Project Overview

```
/root/Projects/buildroot-agent/
├── buildroot-agent/     # C Agent (嵌入式设备端)
│   ├── include/         # Headers (agent.h)
│   ├── src/             # Sources (agent_*.c)
│   └── tests/           # Integration tests
├── buildroot-server/    # Python Server (中央服务器)
│   ├── config/          # Settings (settings.py)
│   ├── handlers/        # Message handlers
│   ├── protocol/        # Message types, codec
│   ├── server/          # WebSocket/Socket servers
│   └── tests/           # Python tests
├── buildroot-web/       # Web Console
│   ├── tests/           # Web tests
│   └── ...
├── scripts/
│   └── test.sh          # Unified test runner
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

### 测试架构

**三端全覆盖真实场景测试：**
- **Server 端**: pytest + pytest-asyncio 进行协议和业务逻辑测试
- **Agent 端**: Shell 脚本 + Python Mock Server 进行端到端测试
- **Web 端**: pytest 检查静态文件和 API 集成

### 测试用例清单

| ID | 测试模块 | 测试项 | 描述 |
|----|---------|--------|------|
| TC-CONN-001 | 连接 | Server 启动 | 启动 Python Server，端口监听成功 |
| TC-CONN-002 | 连接 | Agent 连接 | Agent 成功连接到 Server |
| TC-CONN-003 | 连接 | 设备注册 | Agent 发送 REGISTER，返回 REGISTER_RESULT |
| TC-CONN-004 | 连接 | 心跳机制 | Agent 每 30 秒发送心跳 |
| TC-CONN-005 | 连接 | 自动重连 | Server 重启后 Agent 自动重连 |
| TC-STATUS-001 | 状态 | 系统状态上报 | 自动上报 CPU/内存/磁盘等信息 |
| TC-PTY-001 | PTY | 创建会话 | Web 创建终端会话 |
| TC-PTY-002 | PTY | 数据收发 | 终端输入命令并接收输出 |
| TC-PTY-003 | PTY | 窗口调整 | 调整浏览器窗口大小 |
| TC-FILE-001 | 文件 | 文件上传 | 上传文件到 Agent |
| TC-FILE-002 | 文件 | 文件下载 | 从 Agent 下载文件 |
| TC-FILE-003 | 文件 | 文件列表 | 获取目录文件列表 |
| TC-CMD-001 | 命令 | 命令执行 | 执行远程命令并返回结果 |
| TC-CMD-002 | 命令 | 错误处理 | 执行不存在命令返回错误 |
| TC-PING-001 | Ping | 网络监控 | Ping 配置目标并上报状态 |
| TC-UPDATE-001 | 更新 | 版本检查 | 检查更新并返回版本信息 |

**扩展测试（超出基础清单）：**
| ID | 测试模块 | 测试项 | 描述 |
|----|---------|--------|------|
| TC-STATUS-002 | 状态 | 状态字段完整性 | 验证所有状态字段正确上报 |
| TC-PTY-005 | PTY | 关闭会话 | 关闭终端会话 |
| TC-CONN-007 | 连接 | 多 Agent 连接 | 多个 Agent 同时连接 Server |

### 运行测试

```bash
# 运行全部测试
./scripts/test.sh

# 运行特定端测试
./scripts/test.sh --server       # 仅 Server 端
./scripts/test.sh --agent        # 仅 Agent 端
./scripts/test.sh --web          # 仅 Web 端

# 运行特定测试
./scripts/test.sh --test TC-CONN-003

# 生成报告
./scripts/test.sh --report

# 调试模式（保留测试环境）
./scripts/test.sh --debug
```

### Server 端测试

```bash
cd buildroot-server

# 安装测试依赖
uv add --dev pytest pytest-asyncio pytest-html

# 运行测试
uv run pytest tests/ -v
uv run pytest tests/test_integration.py -v -k "test_register"
uv run pytest tests/ -v --html=report.html
```

### Agent 端测试

**注意**: Agent 端测试框架待完善，目前仅提供基础结构。

```bash
cd buildroot-agent/tests

# 运行集成测试（待实现）
# ./test_integration.sh

# 使用 Mock Server 测试
python mock_server.py &
../build/bin/buildroot-agent -c test_agent.cfg
```

### Web 端测试

**注意**: Web 端测试框架待完善，目前仅提供基础结构。

```bash
cd buildroot-web

# 检查静态文件
python -m pytest tests/test_static.py -v

# 完整测试（需 Server 运行）
python -m pytest tests/ -v
```

### 添加新测试

**Server 端（Python）:**
```python
# tests/handlers/test_new_feature.py
import pytest
from fixtures.mock_agent import MockAgent

@pytest.mark.asyncio
async def test_new_feature(mock_server):
    """TC-NEW-001: 新功能测试"""
    agent = MockAgent()
    await agent.connect("127.0.0.1", 8766)
    
    # 执行测试
    result = await agent.send_message(MSG_TYPE_NEW, data)
    
    # 验证结果
    assert result["status"] == "success"
```

**Agent 端（Shell）:**
```bash
# tests/test_cases/test_new_feature.sh
#!/bin/bash
source ../utils.sh

test_new_feature() {
    log "TC-NEW-001: 测试新功能"
    
    # 启动 Mock Server
    start_mock_server
    
    # 启动 Agent
    start_agent
    
    # 验证结果
    assert_contains "$LOG_FILE" "新功能初始化成功"
    
    cleanup
}

run_test test_new_feature
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
