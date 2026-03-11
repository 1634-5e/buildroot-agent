# ARCHITECTURE.md - 项目架构

## 三端架构

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│                 │   TCP   │                 │   WS    │                 │
│  Agent          │<──────>│   Server        │<──────>│   Web           │
│  (嵌入式设备)    │ Socket │  (中央服务器)    │        │  (管理控制台)   │
│                 │  :8766  │                 │  :8765  │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
      C语言                    Python                     JS/Vue
```

**端口说明：**
- **TCP 8766**: Agent ↔ Server（二进制协议，JSON payload）
- **WebSocket 8765**: Server ↔ Web（JSON 协议）

---

## 组件职责

### Agent (buildroot-agent/) - C 语言

嵌入式设备端代理，运行在目标设备上。

**核心模块：**
| 模块 | 文件 | 职责 |
|------|------|------|
| 主程序 | `main.c` | 程序入口、事件循环 |
| 协议处理 | `agent_protocol.c` | 消息编解码、收发 |
| PTY 管理 | `agent_pty.c` | 终端会话管理 |
| 文件操作 | `agent_file.c` | 文件读写、目录列表 |
| 命令执行 | `agent_cmd.c` | 命令执行、脚本运行 |
| 更新管理 | `agent_update.c` | 远程更新、版本管理 |
| 系统监控 | `agent_status.c` | CPU/内存/磁盘上报 |
| Ping 监控 | `agent_ping.c` | 网络连通性检测 |

**头文件：** `include/agent.h`

### Server (buildroot-server/) - Python

中央服务器，转发消息、管理设备状态。

**核心模块：**
| 模块 | 目录 | 职责 |
|------|------|------|
| 协议定义 | `protocol/` | 消息类型、编解码、数据模型 |
| 消息处理 | `handlers/` | 各类消息的业务逻辑 |
| 服务器 | `server/` | WebSocket/TCP 服务器 |
| 配置 | `config/` | 设置管理 |

**依赖管理：** uv（pyproject.toml）

### Web (buildroot-web/) - JavaScript/Vue

管理控制台，用户界面。

**模块：**
| 模块 | 文件 | 职责 |
|------|------|------|
| 主应用 | `js/app.js` | 应用初始化、设备管理 |
| WebSocket | `js/websocket.js` | 连接管理、消息收发 |
| 终端 | `js/terminal.js` | xterm.js 集成 |
| 工具 | `js/utils.js` | 通用工具函数 |
| 配置 | `js/config.js` | 前端配置 |

---

## 数据流

### 设备注册流程

```
Agent                          Server                      Web
  |                              |                           |
  |-- TCP 连接 ----------------->|                           |
  |-- REGISTER (0xF0) ---------->|                           |
  |   {device_id, version}       |                           |
  |                              |-- 记录设备信息            |
  |                              |-- 广播设备上线 ---------->|
  |                              |                           |
  |-- HEARTBEAT (0x01) --------->|                           |
  |   每 30 秒                    |                           |
```

### PTY 终端流程

```
Web                           Server                      Agent
  |                              |                           |
  |-- WS: PTY_CREATE ----------->|                           |
  |                              |-- TCP: PTY_CREATE ------->|
  |                              |                           |-- 创建 shell
  |                              |<-- PTY_DATA --------------|
  |<-- WS: PTY_DATA -------------|                           |
  |   (终端输出)                  |                           |
  |                              |                           |
  |-- WS: PTY_DATA ------------->|                           |
  |   (用户输入)                  |-- TCP: PTY_DATA --------->|
  |                              |                           |-- 写入 PTY
  |                              |<-- PTY_DATA --------------|
  |<-- WS: PTY_DATA -------------|                           |
```

### 文件操作流程

```
Web                           Server                      Agent
  |                              |                           |
  |-- FILE_REQUEST (0x20) ------>|                           |
  |   {action: "upload",         |                           |
  |    filepath: "/path/file"}   |                           |
  |                              |-- FILE_REQUEST ---------->|
  |                              |                           |-- 读取文件
  |                              |<-- FILE_DATA (0x21) ------|
  |<-- FILE_DATA ----------------|   {content: base64}       |
```

### 更新流程（非强制）

```
Agent                          Server                      Web
  |                              |                           |
  |-- UPDATE_CHECK (0x60) ----->|                           |
  |<-- UPDATE_INFO (0x61) ------|   {has_update: true}      |
  |                              |                           |
  |-- UPDATE_REQUEST_APPROVAL -->|                           |
  |   (等待 PTY 会话创建后)       |-- 广播更新请求 --------->|
  |                              |                           |
  |                              |<-- 批准下载 --------------|
  |<-- UPDATE_APPROVE_DOWNLOAD --|                           |
  |                              |                           |
  |-- 下载 + UPDATE_PROGRESS --->|-- 广播进度 ------------->|
  |                              |                           |
  |-- UPDATE_DOWNLOAD_READY ---->|-- 广播下载完成 --------->|
  |                              |                           |
  |                              |<-- 批准安装 --------------|
  |<-- UPDATE_APPROVE_INSTALL ---|                           |
  |                              |                           |
  |-- 安装 + 重启                |                           |
```

---

## 目录结构

```
buildroot-agent/
├── buildroot-agent/          # C Agent
│   ├── include/              # 头文件
│   │   └── agent.h           # 主头文件（消息类型、结构体）
│   ├── src/                  # 源代码
│   │   ├── main.c            # 入口
│   │   ├── agent_protocol.c  # 协议处理
│   │   ├── agent_pty.c       # PTY 管理
│   │   ├── agent_file.c      # 文件操作
│   │   ├── agent_cmd.c       # 命令执行
│   │   ├── agent_update.c    # 更新管理
│   │   ├── agent_status.c    # 系统状态
│   │   └── agent_ping.c      # Ping 监控
│   ├── tests/                # 测试
│   ├── cmake/                # CMake 配置
│   ├── scripts/              # 构建脚本
│   └── VERSION               # 版本号
│
├── buildroot-server/         # Python Server
│   ├── protocol/             # 协议定义
│   │   ├── constants.py      # 消息类型枚举
│   │   ├── codec.py          # 编解码器
│   │   └── models/           # 数据模型
│   ├── handlers/             # 消息处理器
│   ├── server/               # 服务器实现
│   │   ├── websocket_server.py
│   │   └── tcp_server.py
│   ├── config/               # 配置
│   │   └── settings.py
│   ├── tests/                # 测试
│   ├── main.py               # 入口
│   └── pyproject.toml        # 依赖声明
│
├── buildroot-web/            # Web 控制台
│   ├── index.html            # 主页面
│   ├── js/                   # JavaScript 模块
│   │   ├── app.js
│   │   ├── websocket.js
│   │   ├── terminal.js
│   │   ├── utils.js
│   │   └── config.js
│   ├── css/                  # 样式
│   ├── public/               # 静态资源
│   └── tests/                # 测试
│
├── buildroot-web-vue/        # Vue 版本（可选）
│
├── scripts/                  # 统一脚本
│   ├── test.sh               # 测试运行器
│   ├── build.sh              # Agent 构建
│   └── release.sh            # 发布打包
│
├── postmortem/               # 事后分析文档
│
├── .github/                  # GitHub 配置
│   └── workflows/            # CI/CD
│
├── AGENTS.md                 # AI 助手指引（主文件）
├── ARCHITECTURE.md           # 本文件
├── STYLE.md                  # 代码规范
├── BUILD.md                  # 构建命令
├── TESTING.md                # 测试文档
├── CONSTRAINTS.md            # 硬约束
├── PITFALLS.md               # 常见错误
├── PROTOCOL.md               # 通信协议规范
└── render.yaml               # 部署配置
```

---

## 协议同步点

消息类型定义在两个地方，必须保持同步：

| 语言 | 文件 | 定义方式 |
|------|------|----------|
| C | `buildroot-agent/include/agent.h` | `msg_type_t` 枚举 |
| Python | `buildroot-server/protocol/constants.py` | `MessageType` IntEnum |

**关键消息类型：**
| 类型 | 值 | 用途 |
|------|-----|------|
| HEARTBEAT | 0x01 | 心跳保活 |
| PTY_CREATE | 0x10 | 创建终端 |
| FILE_REQUEST | 0x20 | 文件操作 |
| CMD_REQUEST | 0x30 | 命令执行 |
| REGISTER | 0xF0 | 设备注册 |

**修改协议时：** 必须同时修改两处 + 更新 PROTOCOL.md

---

## 配置管理

### Agent 配置

配置文件：`config.yaml`（可选）

环境变量：`BR_SERVER_` 前缀

```yaml
server:
  host: "192.168.1.100"
  port: 8766
  
device:
  id: "device-001"
  
update:
  check_interval: 86400  # 24小时
  approval_timeout: 300  # 5分钟
```

### Server 配置

配置文件：`buildroot-server/config/settings.py`

环境变量覆盖：

```bash
BR_SERVER_HOST=0.0.0.0
BR_SERVER_WS_PORT=8765
BR_SERVER_TCP_PORT=8766
```

### 数据库

- **开发/测试：** SQLite（自动建表）
- **生产：** PostgreSQL/MySQL（需手动建表或使用 schema.sql）

---

## 扩展点

### 添加新的消息类型

1. 在 PROTOCOL.md 定义消息格式
2. 在 `agent.h` 添加 `MSG_TYPE_XXX`
3. 在 `constants.py` 添加 `MessageType.XXX`
4. 在 Agent 添加处理函数
5. 在 Server 添加 handler
6. 添加测试用例

### 添加新的命令

1. 在 `agent_cmd.c` 的命令表中添加
2. 更新 PROTOCOL.md 的内置命令列表
3. 添加测试用例

### 添加新的文件操作

1. 在 `agent_file.c` 的 action 表中添加
2. 更新 PROTOCOL.md 的 FILE_REQUEST 说明
3. 添加测试用例