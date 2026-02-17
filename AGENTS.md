# AGENTS.md

This file contains guidelines for agentic coding assistants working on this buildroot-agent repository.

## 项目概述

### 目录结构
```
/root/Projects/buildroot-agent/
├── buildroot-agent/     # C Agent (嵌入式设备端)
├── buildroot-server/    # Python Server (中央服务器)
├── buildroot-web/       # Web控制台 (单文件HTML, Vue重构规划中)
├── scripts/             # 项目级脚本
└── PROTOCOL.md          # 通信协议规范
```

### 版本信息 (buildroot-agent运行环境)
- 系统: buildroot2015.08.1
- gcc: 4.9
- cmake: 2.8.12.2
- openssl: 1.1.1

## Build Commands

### C/CMake (buildroot-agent)

```bash
# 配置与构建
cd buildroot-agent && cmake -B build -DCMAKE_BUILD_TYPE=Release -DSTATIC_LINK=ON
cmake --build build                                    # 构建到 build/bin/buildroot-agent

# 快捷脚本
./scripts/build.sh                                     # 本地编译 (x86_64, 静态链接)
./scripts/build.sh --cross                             # 交叉编译 (arm, 静态链接)
./scripts/release.sh                                   # 发布构建 + 打包
./scripts/install.sh /opt/buildroot-agent              # 安装到指定目录

# 清理
rm -rf build                                           # 清理构建产物
```

**构建选项:**
- `-DCMAKE_BUILD_TYPE=Debug` - 启用调试符号和 `DEBUG` 宏
- `-DSTATIC_LINK=ON` - 静态链接 (默认启用, 兼容不同libc)
- `-DCMAKE_TOOLCHAIN_FILE=cmake/arm-buildroot.cmake` - 交叉编译

**注意:** 静态链接二进制约1.4MB, 可在glibc/uClibc系统上运行。

### Python (buildroot-server)

```bash
# 安装依赖
cd buildroot-server && pip install -e .

# 运行服务器
python main.py

# 代码检查与格式化
ruff check .                    # 检查代码问题
ruff check --fix .              # 自动修复
ruff format .                   # 格式化代码
```

### Web (buildroot-web)
当前为单文件HTML (`web_console.html`, ~5600行), 包含嵌入式JS/CSS。
- 依赖: xterm.js, Ace Editor (通过CDN或本地public/)
- Vue 3 + TypeScript 重构规划中

## Code Style Guidelines

### C Code (buildroot-agent)

**命名约定:**
| 类型 | 风格 | 示例 |
|------|------|------|
| 类型/结构体 | `snake_case_t` | `agent_context_t`, `system_status_t` |
| 枚举常量 | `UPPER_CASE` | `MSG_TYPE_HEARTBEAT`, `UPDATE_STATUS_IDLE` |
| 宏定义 | `UPPER_CASE` | `DEFAULT_SERVER_ADDR`, `LOG_LEVEL_INFO` |
| 函数 | `snake_case()` | `agent_init()`, `socket_connect()` |
| 全局变量 | `g_prefix_` | `g_agent_ctx`, `g_log_level` |
| 静态函数 | `static` 关键字 | `static void signal_handler(int sig)` |

**文件组织:**
- 头文件: `include/agent.h`
- 源文件: `src/agent_*.c`

**日志宏:**
```c
LOG_DEBUG("调试信息: %d", value);
LOG_INFO("正常信息");
LOG_WARN("警告信息");
LOG_ERROR("错误信息: %s", strerror(errno));
```

**错误处理:**
- 返回值: 成功返回 `0`, 错误返回 `-1`
- 始终检查系统调用返回值
- 使用 `strerror(errno)` 输出错误详情

**内存管理:**
- 分配: `calloc()` (自动清零)
- 释放: 使用后必须 `free()`
- 字符串: `safe_strncpy()` 防止溢出

**线程安全:**
- 互斥锁: `pthread_mutex_t`
- 操作共享数据前加锁

**注释:** 文档注释使用中文, 代码使用英文

### Python Code (buildroot-server)

**导入顺序:**
1. 标准库
2. 第三方库
3. 本地模块

**命名约定:**
| 类型 | 风格 | 示例 |
|------|------|------|
| 类 | `PascalCase` | `CloudServer`, `FileTransferSession` |
| 函数/变量 | `snake_case` | `handle_connection`, `device_id` |
| 常量 | `UPPER_CASE` | `MESSAGE_HEADER_SIZE` |
| 私有属性 | `_prefix` | `_get_remote_address()` |

**类型注解:**
```python
def get_device(self, device_id: str) -> dict[str, Any] | None:
    ...

name: str | None = None
items: list[dict[str, Any]] = []
```

**数据模型:**
- 使用 Pydantic `BaseModel` 定义消息结构
- 使用 `@dataclass` 定义内部数据类
- 配置类继承 `pydantic_settings.BaseSettings`

**异步模式:**
```python
async def handle_connection(self, reader: StreamReader, writer: StreamWriter):
    try:
        data = await reader.readexactly(3)
        await self._process(data)
    except asyncio.IncompleteReadError:
        logger.info("连接断开")
    except Exception as e:
        logger.error(f"处理错误: {e}")
```

**日志:**
```python
logger = logging.getLogger(__name__)
logger.info(f"设备连接: {device_id}")
logger.debug(f"消息详情: {data}")
logger.error(f"处理失败: {e}")
```

**错误处理:**
- 使用 `try/except` 捕获特定异常
- 避免空 `except:` 块

## Cross-Compilation

工具链文件 `cmake/arm-buildroot.cmake` 配置:
- 编译器: `arm-buildroot-linux-uclibcgnueabi-gcc`
- 目标: ARM + uClibc

```bash
cmake -B build -DCMAKE_TOOLCHAIN_FILE=cmake/arm-buildroot.cmake -DSTATIC_LINK=ON
cmake --build build
```

## Protocol Compatibility

消息类型在两处定义, 必须保持同步:
- C: `buildroot-agent/include/agent.h` (`msg_type_t` 枚举)
- Python: `buildroot-server/protocol/constants.py` (`MessageType` IntEnum)

**十六进制值示例:**
- `0x01` - 心跳
- `0x10` - PTY创建
- `0xF0` - 设备注册

修改协议时, 参考 `PROTOCOL.md` 并同步更新所有定义。