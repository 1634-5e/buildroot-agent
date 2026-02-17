# Buildroot Agent 通信协议规范

> 版本: 1.1.0
> 最后更新: 2024-02-17
> 状态: 正式版

---

## 目录

- [1. 协议概述](#1-协议概述)
- [2. 消息格式](#2-消息格式)
- [3. 消息类型分类](#3-消息类型分类)
- [4. 详细消息定义](#4-详细消息定义)
  - [4.1 基础消息](#41-基础消息)
  - [4.2 PTY消息](#42-pty消息)
  - [4.3 文件传输消息](#43-文件传输消息)
  - [4.4 命令消息](#44-命令消息)
  - [4.5 设备管理](#45-设备管理)
  - [4.6 更新管理](#46-更新管理)
  - [4.7 文件上传消息](#47-文件上传消息)
  - [5. 通信流程](#5-通信流程)
  - [6. 实现规范](#6-实现规范)
  - [7. 已知问题与建议](#7-已知问题与建议)
- [8. 版本历史](#8-版本历史)

---

## 1. 协议概述

### 1.1 协议简介

Buildroot Agent 使用基于 TCP Socket 的二进制协议进行通信，消息采用 JSON 格式作为 payload。该协议支持设备注册、系统监控、文件传输、交互式终端、命令执行和远程更新等功能。

### 1.2 通信架构

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│                 │   TCP   │                 │   WS    │                 │
│  Agent          │<──────>│   Server        │<──────>│   Web           │
│  (嵌入式设备)    │ Socket │  (中央服务器)    │        │  (管理控制台)   │
│                 │         │                 │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

### 1.3 消息流向

- **Agent → Server**: 注册、心跳、系统状态上报、日志上传、脚本执行结果、文件数据
- **Server → Agent**: 注册确认、脚本下发、PTY控制、文件请求、命令执行、更新指令
- **Web → Server**: 设备查询、命令下发、文件操作、PTY会话管理
- **Server → Web**: 设备列表、系统状态、文件列表、PTY数据、命令结果

### 1.4 实现组件

| 组件 | 语言 | 文件位置 |
|------|------|----------|
| Agent | C | `buildroot-agent/include/agent.h`<br>`buildroot-agent/src/agent_protocol.c` |
| Server | Python | `buildroot-server/protocol/constants.py`<br>`buildroot-server/protocol/models/` |
| Web | JavaScript | `buildroot-web/web_console.html` |

---

## 2. 消息格式

### 2.1 二进制封装格式

所有消息遵循统一的二进制封装格式：

```
+--------+-------------------+------------------------+
| Type   | Length            | JSON Data              |
| (1B)   | (2B, Big Endian)  | (Length bytes)         |
+--------+-------------------+------------------------+
```

**字段说明:**

| 字段 | 大小 | 字节序 | 说明 |
|------|------|--------|------|
| Type | 1 byte | - | 消息类型，十六进制值 (0x01-0xFF) |
| Length | 2 bytes | Big Endian | JSON 数据的字节长度 |
| JSON Data | Length bytes | - | UTF-8 编码的 JSON 字符串 |

**最大消息大小:** 65535 字节 (约 64KB)

### 2.2 编码格式

所有消息采用统一编码格式：

```
+--------+--------+--------+
| MsgType| Len[2] | Payload|
| 1 byte | 2 bytes| N bytes|
+--------+--------+--------+
```

**字段说明:**

| 字段 | 大小 | 描述 |
|------|------|------|
| MsgType | 1 byte | 消息类型（十六进制值） |
| Len[2] | 2 bytes | Payload长度（大端序） |
| Payload | N bytes | JSON格式数据 |

**编码示例:**

消息类型 `0x01` (心跳)，JSON数据 `{"timestamp": 1234567890}`：

```
01 00 1B 7B 22 74 69 6D 65 73 74 61 6D 70 22 3A 20 31 32 33 34 35 36 37 38 39 30 7D
```

**解码步骤:**

1. 读取第一个字节作为消息类型
2. 读取第二、三个字节，按大端序计算长度：`length = byte[0] * 256 + byte[1]`
3. 读取后续 N 个字节作为 JSON payload
4. 解析 JSON 数据

---

## 3. 消息类型分类

### 3.1 分类概览

| 分类 | 类型范围 | 用途 |
|------|----------|------|
| 注册消息 | 0xF0-0xF1 | 设备注册 |
| 基础消息 | 0x01-0x05 | 心跳、状态上报、日志、脚本 |
| PTY消息 | 0x10-0x13 | 交互式终端会话 |
| 文件传输 | 0x20-0x27 | 文件读写、列表、打包下载 |
| 文件上传 | 0x40-0x43 | 大文件分块上传 |
| 命令消息 | 0x30-0x31 | 远程命令执行 |
| 设备管理 | 0x50-0x51 | 设备列表和状态管理 |
| 更新管理 | 0x60-0x67 | Agent远程更新 |

### 3.2 完整消息类型表

| 消息类型 | 十六进制 | 名称 | 方向 | 说明 |
|---------|---------|------|------|----|
| HEARTBEAT | 0x01 | 心跳 | 双向 | ✓ | ✓ | ✓ | 保持连接活跃 |
| SYSTEM_STATUS | 0x02 | 系统状态 | Client→Server | ✓ | ✓ | ✓ | 上报系统状态 |
| LOG_UPLOAD | 0x03 | 日志上传 | Client→Server | ✓ | ✓ | ✓ | 上传日志文件 |
| SCRIPT_RECV | 0x04 | 接收脚本 | Server→Client | ✓ | ✓ | ✓ | 下发脚本 |
| SCRIPT_RESULT | 0x05 | 脚本结果 | Client→Server | ✓ | ✓ | ✓ | 返回执行结果 |
| PTY_CREATE | 0x10 | 创建PTY | Server→Client | ✓ | ✓ | ✓ | 创建终端会话 |
| PTY_DATA | 0x11 | PTY数据 | 双向 | ✓ | ✓ | ✓ | 终端数据传输 |
| PTY_RESIZE | 0x12 | PTY调整 | Server→Client | ✓ | ✓ | ✓ | 调整终端大小 |
| PTY_CLOSE | 0x13 | 关闭PTY | 双向 | ✓ | ✓ | ✓ | 关闭终端会话 |
| FILE_REQUEST | 0x20 | 文件请求 | Server→Client | ✓ | ✓ | ✓ | 文件操作请求 |
| FILE_DATA | 0x21 | 文件数据 | Client→Server | ✓ | ✓ | ✓ | 文件数据传输 |
| FILE_LIST_REQUEST | 0x22 | 列表请求 | Server→Client | ✓ | ✓ | ✓ | 请求文件列表 |
| FILE_LIST_RESPONSE | 0x23 | 列表响应 | Client→Server | ✓ | ✓ | ✓ | 返回文件列表 |
| DOWNLOAD_PACKAGE | 0x24 | 打包下载 | 双向 | ✓ | ✓ | ✓ | 文件打包下载 |
| FILE_DOWNLOAD_REQUEST | 0x25 | 下载请求 | Server→Client | ✓ | ✓ | ✗ | TCP下载请求 |
| FILE_DOWNLOAD_DATA | 0x26 | 下载数据 | 双向 | ✓ | ✓ | ✓ | TCP下载数据 |
| CMD_REQUEST | 0x30 | 命令请求 | Server→Client | ✓ | ✓ | ✓ | 执行命令 |
| CMD_RESPONSE | 0x31 | 命令响应 | Client→Server | ✓ | ✓ | ✓ | 命令执行结果 |
| DEVICE_LIST | 0x50 | 设备列表 | 双向 | ✓ | ✓ | ✓ | 设备列表查询 |
| DEVICE_DISCONNECT | 0x51 | 设备断开 | Server→Client | ✓ | ✓ | ✓ | 设备断开通知 |
| UPDATE_CHECK | 0x60 | 更新检查 | Client→Server | ✓ | ✓ | ✗ | 检查更新 |
| UPDATE_INFO | 0x61 | 更新信息 | Server→Client | ✓ | ✓ | ✗ | 更新信息 |
| UPDATE_DOWNLOAD | 0x62 | 更新下载 | Client→Server | ✓ | ✓ | ✗ | 下载更新 |
| UPDATE_PROGRESS | 0x63 | 更新进度 | Client→Server | ✓ | ✓ | ✗ | 更新进度 |
| UPDATE_APPROVE | 0x64 | 更新批准 | Server→Client | ✓ | ✓ | ✗ | 批准下载 |
| UPDATE_COMPLETE | 0x65 | 更新完成 | Server→Client | ✓ | ✓ | ✗ | 更新完成 |
| UPDATE_ERROR | 0x66 | 更新错误 | 双向 | ✓ | ✓ | ✗ | 更新错误 |
| UPDATE_ROLLBACK | 0x67 | 更新回滚 | Server→Client | ✓ | ✓ | ✗ | 回滚更新 |

---

## 4. 详细消息定义

 ### 4.1 基础消息

#### REGISTER (0xF0) - 设备注册

**方向:** Client (Agent) → Server

**描述:** 设备连接后立即发送，用于向服务器注册设备身份。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| device_id | string | 是 | - | 设备唯一标识ID |
| version | string | 否 | - | Agent版本号 |

**示例:**
```json
{
  "device_id": "HTCU-开发板-001",
  "version": "1.0.0"
}
```

**注意事项:**
- 必须在连接建立后立即发送
- 服务器不进行密码验证（注册模式）
- 每个device_id应该唯一

---

#### REGISTER_RESULT (0xF1) - 注册结果

**方向:** Server → Client (Agent)

**描述:** 服务器返回注册结果（预留，当前未使用）。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| success | boolean | 是 | - | 注册是否成功 |
| message | string | 否 | - | 结果描述 |

**示例:**
```json
{
  "success": true,
  "message": "注册成功"
}
```

---

#### HEARTBEAT (0x01) - 心跳

**方向:** 双向 (Client↔Server)

**描述:** 用于保持连接活跃，检测连接状态。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| timestamp | int64 | 否 | - | 时间戳 |
| uptime | uint32 | 否 | - | 运行时间（秒） |

**示例:**
```json
{
  "timestamp": 1708000000000,
  "uptime": 3600
}
```


#### SYSTEM_STATUS (0x02) - 系统状态

**方向:** Client (Agent) → Server

**描述:** Agent 定期上报系统状态信息。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| cpu_usage | float | 是 | - | CPU 使用率 (0-100) |
| cpu_cores | int | 是 | - | CPU 核心数 |
| cpu_user | float | 是 | - | 用户态 CPU 使用率 |
| cpu_system | float | 是 | - | 系统态 CPU 使用率 |
| mem_total | float | 是 | - | 总内存 (MB) |
| mem_used | float | 是 | - | 已用内存 (MB) |
| mem_free | float | 是 | - | 空闲内存 (MB) |
| disk_total | float | 是 | - | 磁盘总量 (MB) |
| disk_used | float | 是 | - | 磁盘已用 (MB) |
| load_1min | float | 是 | - | 1分钟负载 |
| load_5min | float | 是 | - | 5分钟负载 |
| load_15min | float | 是 | - | 15分钟负载 |
| uptime | uint32 | 是 | - | 运行时间 (秒) |
| net_rx_bytes | int32 | 是 | - | 网络接收字节数 |
| net_tx_bytes | int32 | 是 | - | 网络发送字节数 |
| hostname | string | 是 | - | 主机名 |
| kernel_version | string | 是 | - | 内核版本 |
| ip_addr | string | 是 | - | IP 地址 |
| mac_addr | string | 是 | - | MAC 地址 |
| request_id | string | 否 | - | 请求 ID（响应式查询时） |

**示例:**
```json
{
  "cpu_usage": 45.2,
  "cpu_cores": 4,
  "cpu_user": 30.5,
  "cpu_system": 14.7,
  "mem_total": 4096.0,
  "mem_used": 2048.0,
  "mem_free": 2048.0,
  "disk_total": 102400.0,
  "disk_used": 51200.0,
  "load_1min": 1.2,
  "load_5min": 1.5,
  "load_15min": 1.3,
  "uptime": 3600,
  "net_rx_bytes": 1048576,
  "net_tx_bytes": 524288,
  "hostname": "device-001",
  "kernel_version": "4.9.123",
  "ip_addr": "192.168.1.100",
  "mac_addr": "00:11:22:33:44:55",
  "request_id": "req-123456"
}
```

---

#### LOG_UPLOAD (0x03) - 日志上传

**方向:** Client (Agent) → Server

**描述:** 上传日志文件内容或日志行。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| filepath | string | 是 | - | 日志文件路径 |
| chunk | int | 否 | - | 当前块编号（分块传输） |
| total_chunks | int | 否 | 1 | 总块数 |
| line | string | 否 | - | 日志行内容 |
| lines | int | 否 | - | 行数 |
| content | string | 否 | - | 文件内容（base64编码） |
| request_id | string | 否 | - | 请求 ID |

**示例:**
```json
{
  "filepath": "/var/log/app.log",
  "content": "SGVsbG8gV29ybGQ=",
  "request_id": "req-123456"
}
```


#### SCRIPT_RECV (0x04) - 接收脚本

**方向:** Server → Client (Agent)

**描述:** 服务器向 Agent 下发脚本执行。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| script_id | string | 是 | - | 脚本唯一标识 |
| content | string | 否 | - | 脚本内容（内联脚本） |
| filename | string | 否 | - | 文件名（已保存脚本） |
| execute | boolean | 否 | true | 是否立即执行 |

**使用场景:**

1. **内联脚本执行:**
```json
{
  "script_id": "script-001",
  "content": "#!/bin/bash\necho 'Hello World'",
  "execute": true
}
```

2. **仅保存不执行:**
```json
{
  "script_id": "script-001",
  "content": "#!/bin/bash\necho 'Hello World'",
  "filename": "hello.sh",
  "execute": false
}
```

3. **执行已保存脚本:**
```json
{
  "script_id": "script-001",
  "filename": "hello.sh",
  "execute": true
}
```


#### SCRIPT_RESULT (0x05) - 脚本执行结果

**方向:** Client (Agent) → Server

**描述:** Agent 返回脚本执行结果。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| script_id | string | 是 | - | 脚本 ID |
| exit_code | int | 是 | -1 | 退出码 |
| success | boolean | 否 | false | 是否成功 |
| output | string | 否 | - | 输出内容（stdout + stderr） |
| request_id | string | 否 | - | 请求 ID |

**示例:**
```json
{
  "script_id": "script-001",
  "exit_code": 0,
  "success": true,
  "output": "Hello World\n",
  "request_id": "req-123456"
}
```


### 4.2 PTY消息

#### PTY_CREATE (0x10) - 创建 PTY 会话

**方向:** Server → Client (Agent)

**描述:** 创建一个交互式终端会话。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| session_id | int | 是 | - | 会话 ID（支持 `sessionId` 兼容） |
| rows | int | 否 | 24 | 终端行数 |
| cols | int | 否 | 80 | 终端列数 |

**命名兼容性:**
- C 代码同时支持 `session_id` 和 `sessionId` 两种命名
- 推荐：使用 `session_id`

**示例:**
```json
{
  "session_id": 1,
  "rows": 24,
  "cols": 80
}
```


#### PTY_DATA (0x11) - PTY 数据传输

**方向:** 双向 (Client↔Server)

**描述:** 传输 PTY 会话的数据（输入/输出）。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| session_id | int | 是 | - | 会话 ID |
| data | string | 是 | - | PTY 数据（base64 编码） |

**示例:**
```json
{
  "session_id": 1,
  "data": "bHM="
}
```


#### PTY_RESIZE (0x12) - PTY 窗口调整

**方向:** Server → Client (Agent)

**描述:** 调整 PTY 终端窗口大小。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| session_id | int | 是 | - | 会话 ID |
| rows | int | 否 | 24 | 新的行数 |
| cols | int | 否 | 80 | 新的列数 |

**示例:**
```json
{
  "session_id": 1,
  "rows": 30,
  "cols": 120
}
```


#### PTY_CLOSE (0x13) - 关闭 PTY 会话

**方向:** 双向 (Client↔Server)

**描述:** 关闭 PTY 会话。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| session_id | int | 是 | - | 会话 ID |
| reason | string | 否 | "unknown" | 关闭原因 |

**示例:**
```json
{
  "session_id": 1,
  "reason": "user_closed"
}
```


### 4.3 文件传输消息

#### FILE_REQUEST (0x20) - 文件操作请求

**方向:** Server → Client (Agent)

**描述:** 请求执行文件操作。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| action | string | 是 | - | 操作类型 |
| filepath | string | 条件 | - | 文件路径（大部分操作需要） |
| request_id | string | 否 | - | 请求 ID |
| lines | int | 否 | 100 | 行数（tail 操作） |
| offset | int | 否 | 0 | 偏移量（read 操作） |
| length | int | 否 | - | 读取长度（read 操作） |
| content | string | 条件 | - | 文件内容（write 操作，base64） |
| mtime | int64 | 否 | - | 修改时间（write 操作） |
| force | boolean | 否 | false | 强制写入（write 操作） |

**支持的操作:**

| action | 描述 | 需要字段 | 响应消息 |
|--------|------|----------|----------|
| upload | 上传文件 | filepath | FILE_DATA |
| tail | 读取文件末尾 | filepath, lines | FILE_DATA |
| watch | 监控文件 | filepath | FILE_DATA (持续) |
| unwatch | 停止监控 | filepath | - |
| list | 列出目录 | path | FILE_LIST_RESPONSE |
| read | 读取文件 | filepath, offset, length | FILE_DATA |
| write | 写入文件 | filepath, content, mtime, force | FILE_DATA |

**示例:**

1. **上传文件:**
```json
{
  "action": "upload",
  "filepath": "/var/log/app.log",
  "request_id": "req-123456"
}
```

2. **读取文件末尾:**
```json
{
  "action": "tail",
  "filepath": "/var/log/app.log",
  "lines": 100,
  "request_id": "req-123456"
}
```

3. **写入文件:**
```json
{
  "action": "write",
  "filepath": "/tmp/test.txt",
  "content": "SGVsbG8gV29ybGQ=",
  "mtime": 1708000000000,
  "force": true,
  "request_id": "req-123456"
}
```


#### FILE_DATA (0x21) - 文件数据

**方向:** Client (Agent) → Server

**描述:** 返回文件数据或操作结果。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| filepath | string | 否 | - | 文件路径 |
| content | string | 否 | - | 文件内容（base64 编码） |
| request_id | string | 否 | - | 请求 ID |
| chunk_index | int | 否 | 0 | 块索引（分块传输） |
| total_chunks | int | 否 | 1 | 总块数 |
| error | string | 否 | - | 错误信息（如果失败） |
| line | string | 否 | - | 日志行内容 |
| is_final | boolean | 否 | true | 是否最后一块 |
| size | int | 否 | - | 文件大小 |

**示例:**

成功响应:
```json
{
  "filepath": "/var/log/app.log",
  "content": "SGVsbG8gV29ybGQ=",
  "size": 11,
  "request_id": "req-123456"
}
```

错误响应:
```json
{
  "filepath": "/var/log/app.log",
  "error": "文件不存在",
  "request_id": "req-123456"
}
```


#### FILE_LIST_REQUEST (0x22) - 文件列表请求

**方向:** Server → Client (Agent)

**描述:** 请求列出目录内容。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| path | string | 否 | "/" | 目录路径 |
| request_id | string | 否 | - | 请求 ID |

**示例:**
```json
{
  "path": "/root",
  "request_id": "req-123456"
}
```


#### FILE_LIST_RESPONSE (0x23) - 文件列表响应

**方向:** Client (Agent) → Server

**描述:** 返回目录内容列表（支持分块传输）。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| path | string | 是 | - | 目录路径 |
| files | array | 是 | - | 文件列表 |
| files[].name | string | 是 | - | 文件名 |
| files[].path | string | 是 | - | 完整路径 |
| files[].is_dir | int | 是 | - | 是否为目录 (0/1) |
| files[].size | int | 是 | - | 文件大小（字节） |
| chunk | int | 是 | 0 | 当前块编号 |
| total_chunks | int | 是 | 1 | 总块数 |
| request_id | string | 是 | - | 请求 ID |

**分块策略:**
- 每个chunk最多 20 个文件
- WebSocket 消息最大 65534 字节
- 使用 `chunk` 和 `total_chunks` 字段实现分块

**示例:**

单个chunk:
```json
{
  "path": "/root",
  "files": [
    {"name": "file1.txt", "path": "/root/file1.txt", "is_dir": 0, "size": 1024},
    {"name": "file2.txt", "path": "/root/file2.txt", "is_dir": 0, "size": 2048},
    {"name": "docs", "path": "/root/docs", "is_dir": 1, "size": 4096}
  ],
  "chunk": 0,
  "total_chunks": 1,
  "request_id": "req-123456"
}
```

多个chunk (第一块):
```json
{
  "path": "/root",
  "files": [/* 20 个文件 */],
  "chunk": 0,
  "total_chunks": 3,
  "request_id": "req-123456"
}
```


#### DOWNLOAD_PACKAGE (0x24) - 打包下载

**方向:** 双向 (Client↔Server)

**描述:** 文件打包并下载（支持多文件）。

**Server → Client (请求):**
```json
{
  "path": "/var/log",
  "format": "tar",
  "request_id": "req-123456"
}
```

或多个文件:
```json
{
  "paths": ["/var/log/app.log", "/etc/config.conf"],
  "format": "zip",
  "request_id": "req-123456"
}
```

**Client → Server (响应，分块):**
```json
{
  "filename": "archive.tar",
  "size": 1024000,
  "content": "base64data...",
  "chunk_index": 0,
  "total_chunks": 5,
  "request_id": "req-123456",
  "complete": false
}
```

最后一块:
```json
{
  "chunk_index": 4,
  "total_chunks": 5,
  "request_id": "req-123456"
}
```

**数据结构:**

| 字段名 | 类型 | 必选 | 方向 | 描述 |
|--------|------|------|------|------|
| path | string | 条件 | → | 单个文件/目录路径 |
| paths | array | 条件 | → | 多个文件路径 |
| format | string | 否 | → | 归档格式 (tar/zip) |
| request_id | string | 否 | → | 请求 ID |
| filename | string | 否 | ← | 归档文件名 |
| size | int | 否 | ← | 文件总大小 |
| content | string | 否 | ← | 内容（base64） |
| chunk_index | int | 否 | ← | 当前块索引 |
| total_chunks | int | 否 | ← | 总块数 |
| complete | boolean | 否 | ← | 是否完成 |

**分块策略:**
- 每个 chunk 最大 48KB base64 数据
- 第一块包含 `filename` 和 `size`
- 最后一块设置 `complete: true`


#### FILE_DOWNLOAD_REQUEST (0x25) - TCP 下载请求

**方向:** Server → Client (Agent)

**描述:** 请求 Agent 通过 TCP 下载文件。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| file_path | string | 是 | - | 文件路径 |
| output_path | string | 是 | - | 输出路径 |
| offset | int64 | 否 | 0 | 断点续传位置 |
| chunk_size | int | 否 | 16384 | 块大小 |
| timeout | int | 否 | - | 超时设置（秒） |
| max_retries | int | 否 | - | 最大重试次数 |
| request_id | string | 否 | - | 请求 ID |

**示例:**
```json
{
  "file_path": "/large/file.tar.gz",
  "output_path": "/tmp/downloaded.tar.gz",
  "offset": 0,
  "chunk_size": 16384,
  "request_id": "req-123456"
}
```

---

#### FILE_DOWNLOAD_DATA (0x26) - TCP 下载数据

**方向:** 双向 (Client↔Server)

**描述:** TCP 下载的数据传输。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| file_path | string | 是 | - | 文件路径 |
| offset | int64 | 是 | - | 当前偏移量 |
| data | string | 是 | - | 数据（base64） |
| size | int | 否 | - | 数据块大小 |
| is_final | boolean | 否 | false | 是否最后一块 |
| total_size | int64 | 否 | - | 文件总大小 |
| request_id | string | 否 | - | 请求 ID |

---

### 4.4 命令消息

#### CMD_REQUEST (0x30) - 命令请求

**方向:** Server → Client (Agent)

**描述:** 请求 Agent 执行命令。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| cmd | string | 是 | - | 命令 |
| request_id | string | 否 | - | 请求 ID |

**内置命令:**

| 命令 | 描述 |
|------|------|
| status | 查询系统状态 |
| system_status | 查询系统状态（同上） |
| reboot | 重启设备 |
| pty_list | 列出 PTY 会话 |
| script_list | 列出脚本 |
| 其他 | 执行 shell 命令 |

**示例:**

1. **内置命令 - 系统状态:**
```json
{
  "cmd": "status",
  "request_id": "req-123456"
}
```

2. **内置命令 - 重启:**
```json
{
  "cmd": "reboot"
}
```

3. **Shell 命令:**
```json
{
  "cmd": "ls -la /root",
  "request_id": "req-123456"
}
```


#### CMD_RESPONSE (0x31) - 命令响应

**方向:** Client (Agent) → Server

**描述:** 返回命令执行结果。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| request_id | string | 否 | - | 请求 ID |
| exit_code | int | 是 | -1 | 退出码 |
| success | boolean | 否 | false | 是否成功 |
| stdout | string | 否 | - | 标准输出 |
| stderr | string | 否 | - | 标准错误输出 |
| script_id | string | 否 | - | 脚本 ID（如果执行的是脚本） |

**示例:**

成功:
```json
{
  "request_id": "req-123456",
  "exit_code": 0,
  "success": true,
  "stdout": "file1.txt\nfile2.txt\n"
}
```

失败:
```json
{
  "request_id": "req-123456",
  "exit_code": 127,
  "success": false,
  "stderr": "command not found: invalid_cmd"
}
```


### 4.5 设备管理

#### DEVICE_LIST (0x50) - 设备列表

**方向:** 双向 (Client↔Server)

**描述:** 查询或推送设备列表。

**请求 (Web → Server):**
```json
{
  "action": "get_list",
  "page": 0,
  "page_size": 20,
  "search_keyword": "",
  "sort_by": "device_id",
  "sort_order": "asc"
}
```

**响应 (Server → Web):**
```json
{
  "devices": [
    {
      "device_id": "device-001",
      "name": "Device 1",
      "ip_addr": "192.168.1.100",
      "status": "online",
      "last_seen": "2024-02-16T10:00:00Z"
    }
  ],
  "total_count": 10,
  "page": 0,
  "page_size": 20
}
```

**数据结构:**

| 字段名 | 类型 | 必选 | 方向 | 描述 |
|--------|------|------|------|------|
| action | string | 是 | → | 操作类型 (get_list) |
| page | int | 否 | → | 页码（默认0） |
| page_size | int | 否 | → | 每页大小（默认20） |
| search_keyword | string | 否 | → | 搜索关键词 |
| sort_by | string | 否 | → | 排序字段 |
| sort_order | string | 否 | → | 排序顺序 (asc/desc) |
| devices | array | 是 | ← | 设备列表 |
| devices[].device_id | string | 是 | ← | 设备 ID |
| devices[].name | string | 否 | ← | 设备名称 |
| devices[].ip_addr | string | 否 | ← | IP 地址 |
| devices[].status | string | 否 | ← | 状态 (online/offline) |
| devices[].last_seen | string | 否 | ← | 最后在线时间 (ISO 8601) |
| total_count | int | 是 | ← | 总数量 |
| count | int | 是 | ← | 设备数量（Python 兼容） |


#### DEVICE_DISCONNECT (0x51) - 设备断开通知

**方向:** Server → Web (Client)

**描述:** 通知客户端设备断开连接。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| device_id | string | 是 | - | 设备 ID |
| reason | string | 是 | - | 断开原因 |

**示例:**
```json
{
  "device_id": "device-001",
  "reason": "connection_timeout"
}
```

---

### 4.6 更新管理

> **注意:** 更新管理消息仅在 Agent (C) 和 Server (Python) 之间使用，Web (JavaScript) 不参与。

#### UPDATE_CHECK (0x60) - 更新检查

**方向:** Client (Agent) → Server

**描述:** Agent 请求检查是否有新版本。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| current_version | string | 是 | - | 当前版本 |
| channel | string | 否 | "stable" | 更新渠道 (stable/beta/dev) |

**示例:**
```json
{
  "current_version": "1.2.3",
  "channel": "stable"
}
```


#### UPDATE_INFO (0x61) - 更新信息

**方向:** Server → Client (Agent)

**描述:** 服务器返回更新信息。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| has_update | boolean | 是 | false | 是否有更新 |
| current_version | string | 否 | - | 当前版本 |
| latest_version | string | 否 | - | 最新版本 |
| channel | string | 否 | "stable" | 更新渠道 |
| file_size | int | 否 | 0 | 文件大小（字节） |
| download_url | string | 是 | - | 下载 URL |
| md5_checksum | string | 是 | - | MD5 校验和 |
| sha256_checksum | string | 否 | - | SHA256 校验和 |
| sha512_checksum | string | 否 | - | SHA512 校验和 |
| release_notes | string | 否 | - | 更新说明 |
| mandatory | boolean | 否 | false | 是否强制更新 |
| release_date | string | 否 | - | 发布日期 |
| changes | array | 否 | [] | 变更列表 |
| request_id | string | 否 | - | 请求 ID |

**示例:**

有更新:
```json
{
  "has_update": true,
  "current_version": "1.2.3",
  "latest_version": "1.3.0",
  "channel": "stable",
  "version_code": 13000,
  "file_size": 10485760,
  "download_url": "https://example.com/updates/agent-1.3.0.tar",
  "md5_checksum": "abc123...",
  "sha256_checksum": "def456...",
  "release_notes": "Bug fixes and improvements",
  "mandatory": false,
  "release_date": "2024-02-16",
  "changes": ["Fix issue #123", "Add new feature"],
  "request_id": "req-123456"
}
```

无更新:
```json
{
  "has_update": false
}
```


#### UPDATE_DOWNLOAD (0x62) - 下载更新

**方向:** Client (Agent) → Server

**描述:** Agent 请求下载更新包。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| version | string | 是 | - | 目标版本 |
| request_id | string | 是 | - | 请求 ID |

**示例:**
```json
{
  "version": "1.3.0",
  "request_id": "update-123456"
}
```


#### UPDATE_PROGRESS (0x63) - 更新进度

**方向:** Client (Agent) → Server

**描述:** 上报更新进度和状态。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| status | string | 是 | - | 状态 |
| progress | int | 否 | 0 | 进度百分比 (0-100) |
| message | string | 否 | - | 消息 |
| request_id | string | 否 | - | 请求 ID |
| path | string | 否 | - | 文件路径（部分状态） |
| error | string | 否 | - | 错误信息（失败状态） |

**状态值:**

| status | 描述 |
|--------|------|
| checking | 正在检查更新 |
| downloading | 正在下载 |
| verifying | 正在验证 |
| backing_up | 正在备份 |
| installing | 正在安装 |
| restarting | 正在重启 |
| complete | 完成 |
| failed | 失败 |
| rolling_back | 正在回滚 |
| rollback_complete | 回滚完成 |

**示例:**

下载中:
```json
{
  "status": "downloading",
  "progress": 45,
  "message": "正在下载...",
  "request_id": "update-123456"
}
```

下载完成:
```json
{
  "status": "downloaded",
  "request_id": "update-123456",
  "progress": 100
}
```

安装中:
```json
{
  "status": "installing",
  "request_id": "update-123456",
  "path": "/tmp/update.tar"
}
```


#### UPDATE_APPROVE (0x64) - 更新批准

**方向:** Server → Client (Agent)

**描述:** 服务器批准下载并提供下载 URL。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| status | string | 是 | - | 批准状态 |
| download_url | string | 是 | - | 下载 URL |
| version | string | 否 | - | 版本号 |
| file_size | int | 否 | 0 | 文件大小 |
| md5_checksum | string | 否 | - | MD5 校验和 |
| sha256_checksum | string | 否 | - | SHA256 校验和 |
| request_id | string | 是 | - | 请求 ID |
| mandatory | boolean | 否 | false | 是否强制 |
| approval_time | string | 否 | - | 批准时间 |

**示例:**
```json
{
  "status": "approved",
  "download_url": "https://example.com/updates/agent-1.3.0.tar",
  "version": "1.3.0",
  "file_size": 10485760,
  "md5_checksum": "abc123...",
  "sha256_checksum": "def456...",
  "request_id": "update-123456",
  "mandatory": false,
  "approval_time": "2024-02-16T10:00:00Z"
}
```


#### UPDATE_COMPLETE (0x65) - 更新完成

**方向:** Server → Client (Agent)

**描述:** 服务器通知更新完成，Agent 应重启。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| version | string | 是 | - | 新版本号 |
| success | boolean | 是 | true | 是否成功 |
| message | string | 否 | - | 消息 |
| request_id | string | 否 | - | 请求 ID |

**示例:**
```json
{
  "version": "1.3.0",
  "success": true,
  "message": "更新成功",
  "request_id": "update-123456"
}
```

**Agent 行为:**
- 收到此消息后，等待 2 秒
- 调用 `update_restart_agent()` 重启


#### UPDATE_ERROR (0x66) - 更新错误

**方向:** 双向 (Client↔Server)

**描述:** 报告更新过程中的错误。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| error | string | 是 | - | 错误信息 |
| status | string | 是 | - | 状态 |
| request_id | string | 否 | - | 请求 ID |

**示例:**
```json
{
  "status": "failed",
  "error": "download_failed",
  "request_id": "update-123456"
}
```

**Agent 行为:**
- 如果配置了 `update_rollback_on_fail`，自动执行回滚


#### UPDATE_ROLLBACK (0x67) - 更新回滚

**方向:** Server → Client (Agent)

**描述:** 服务器通知 Agent 回滚到旧版本。

**数据结构:**

| 字段名 | 类型 | 必选 | 默认值 | 描述 |
|--------|------|------|--------|------|
| backup_path | string | 否 | - | 备份路径 |
| backup_version | string | 否 | - | 备份版本 |
| reason | string | 否 | - | 回滚原因 |
| success | boolean | 否 | true | 是否成功 |

**示例:**
```json
{
  "backup_path": "/var/lib/agent/backup/agent-1.2.3",
  "backup_version": "1.2.3",
  "reason": "update_failed",
  "success": true
}
```

**Agent 行为:**
- 如果 `backup_path` 为空，尝试自动回滚到最近备份


## 5. 通信流程

### 5.1 注册流程

```
Agent                          Server
  |                              |
  |-- TCP Socket 连接 --------->|
  |                              |
  |-- REGISTER (0xF0) --------->|
  |   {device_id, version}       |  添加设备到设备列表
  |                              |  标记设备为已注册
  |                              |
  |<-- [连接成功] ------------|
  |                              |
  |-- HEARTBEAT (0x01) ------->|
  |   {timestamp, uptime}        |  开始心跳保持
  |                              |
  |<-- HEARTBEAT (0x01) -------|
```

**说明:**
- 设备连接后立即发送 REGISTER 消息进行注册
- 包含设备ID和版本信息
- 服务器收到后添加到设备列表
- 无需密码或token验证（注册模式）
- 注册成功后开始心跳保活

### 5.2 PTY 会话流程

```
Web                           Server                      Agent
  |                              |                            |
  |-- PTY_CREATE (0x10) -------->|                            |
  |   {session_id, rows, cols}  |                            |
  |                              |--- PTY_CREATE (0x10) ----->|
  |                              |                            |-- 创建 PTY
  |                              |                            |
  |                              |<-- PTY_DATA (0x11) --------|
  |                              |   {session_id, data}       |
  |                              |                            |
  |<-- PTY_DATA (0x11) ----------|                            |
  |   {session_id, data}         |                            |
  |                              |                            |
  |-- PTY_DATA (0x11) ---------->|                            |
  |   {session_id, data}         |--- PTY_DATA (0x11) ------>|
  |                              |                            |-- 写入 PTY
  |                              |                            |
  |                              |<-- PTY_DATA (0x11) --------|
  |                              |                            |
  |<-- PTY_DATA (0x11) ----------|                            |
  |                              |                            |
  |-- PTY_RESIZE (0x12) -------->|                            |
  |   {session_id, rows, cols}  |--- PTY_RESIZE (0x12) ----->|
  |                              |                            |-- 调整窗口大小
  |                              |                            |
  |-- PTY_CLOSE (0x13) --------->|                            |
  |   {session_id, reason}       |--- PTY_CLOSE (0x13) ------>|
  |                              |                            |-- 关闭 PTY
```

**会话超时:**
- Agent 的 PTY 会话有超时机制
- 30 分钟无活动自动关闭

---

### 5.3 文件传输流程

#### 5.3.1 文件上传（读取）

```
Web                           Server                      Agent
 |                              |                            |
 |-- FILE_REQUEST (0x20) ------>|                            |
 |   {action: "upload",        |                            |
 |    filepath}                 |                            |
 |                              |--- FILE_REQUEST (0x20) --->|
 |                              |                            |-- 读取文件
 |                              |                            |
 |                              |<-- FILE_DATA (0x21) -------|
 |                              |   {filepath, content}     |
 |                              |                            |
 |<-- FILE_DATA (0x21) ---------|                            |
 |   {filepath, content}        |                            |
```

#### 5.3.2 文件列表

```
Web                           Server                      Agent
 |                              |                            |
 |-- FILE_LIST_REQUEST (0x22) ->|                            |
 |   {path}                     |                            |
 |                              |--- FILE_LIST_REQUEST ----->|
 |                              |                            |-- 读取目录
 |                              |                            |
 |                              |<-- FILE_LIST_RESPONSE (0x23) (chunk 0) |
 |                              |<-- FILE_LIST_RESPONSE (0x23) (chunk 1) |
 |                              |<-- FILE_LIST_RESPONSE (0x23) (chunk 2) |
 |                              |                            |
 |<-- 合并 chunks --------------->|                            |
```

**分块策略:**
- 每个 chunk 最多 20 个文件
- Server 端合并所有 chunks 后返回给 Web

#### 5.3.3 文件下载（打包）

```
Web                           Server                      Agent
 |                              |                            |
 |-- DOWNLOAD_PACKAGE (0x24) -->|                            |
 |   {path, format}             |                            |
 |                              |--- DOWNLOAD_PACKAGE (0x24) ->|
 |                              |                            |-- 打包文件
 |                              |                            |
 |                              |<-- DOWNLOAD_PACKAGE (chunk 0) |
 |                              |<-- DOWNLOAD_PACKAGE (chunk 1) |
 |                              |<-- DOWNLOAD_PACKAGE (chunk 2) |
 |                              |                            |
 |<-- 合并 chunks --------------->|                            |
```

---

### 5.4 更新流程

```
Agent                          Server
  |                              |
  |-- UPDATE_CHECK (0x60) ------>|
  |   {current_version, channel} |
  |                              |-- 检查版本
  |                              |
  |<-- UPDATE_INFO (0x61) -------|
  |   {has_update: "true",      |
  |    latest_version, ...}      |
  |                              |
  |-- UPDATE_DOWNLOAD (0x62) --->|  (或自动请求)
  |   {version, request_id}      |
  |                              |-- 批准下载
  |                              |
  |<-- UPDATE_APPROVE (0x64) ----|
  |   {download_url, ...}        |
  |                              |
  |-- 开始下载 ------------------->|
  |                              |
  |-- UPDATE_PROGRESS (0x63) --->|
  |   {status: "downloading",    |
  |    progress: 50}             |
  |                              |
  |-- UPDATE_PROGRESS (0x63) --->|
  |   {status: "installing"}     |
  |                              |
  |<-- UPDATE_COMPLETE (0x65) ---|
  |   {version, success}         |
  |                              |
  |-- 重启 Agent ---------------->|
```

**自动更新逻辑:**
1. 如果配置 `update_require_confirm=false` 或 `mandatory=true`，自动请求下载
2. 否则等待服务器批准（UPDATE_APPROVE）
3. 下载完成后自动安装
4. 安装成功后重启 Agent
5. 如果失败且配置了 `update_rollback_on_fail`，自动回滚

---

## 6. 实现规范

### 6.1 命名规范

#### 字段命名
- **推荐:** snake_case（下划线命名）
- **禁止:** 驼峰命名，除非兼容性需求

**示例:**
```json
{
  "session_id": 1,        // ✓ 推荐
  "sessionId": 1,         // ✗ 避免（除非兼容）
  "device_id": "dev-001", // ✓ 推荐
  "request_id": "req-123" // ✓ 推荐
}
```

#### 兼容性处理
- C 代码已实现兼容两种命名
- 推荐：逐步统一为 snake_case

**C 代码示例:**
```c
int session_id = json_get_int(data, "sessionId", -1);
if (session_id < 0) {
    session_id = json_get_int(data, "session_id", -1);
}
```

### 6.2 数据类型规范

#### 布尔值
- JSON 中使用 `true/false`
- 避免字符串 "true"/"false"

**例外:**
- `UPDATE_INFO.has_update` 使用字符串（历史遗留）
- 建议：改为布尔值

#### 时间戳
- 使用 Unix 时间戳（毫秒）
- 类型: `int64`

**示例:**
```json
{
  "timestamp": 1708000000000,
  "mtime": 1708000000000
}
```

#### Base64 编码
- 文件内容必须 Base64 编码
- 使用标准 Base64（不包含 URL 安全字符）

**示例:**
```json
{
  "content": "SGVsbG8gV29ybGQ="
}
```

### 6.3 分块传输策略

#### FILE_LIST_RESPONSE
- 每个chunk最多 20 个文件
- 使用 `chunk` 和 `total_chunks` 字段

#### DOWNLOAD_PACKAGE
- 每个chunk最大 48KB base64 数据
- 第一块包含 `filename` 和 `size`
- 最后一块设置 `complete: true`

#### 通用规则
- WebSocket 消息最大 65534 字节
- 估算: 每个文件约 200-300 字节
- 建议保守估计，预留 512 字节头部空间

### 6.4 错误处理

#### 错误响应格式
```json
{
  "error": "error_type",
  "message": "Human readable error message",
  "request_id": "req-123456"
}
```

#### 常见错误类型

| error_type | 描述 |
|------------|------|
| file_not_found | 文件不存在 |
| permission_denied | 权限不足 |
| invalid_request | 无效的请求 |
| authentication_failed | 认证失败 |
| download_failed | 下载失败 |
| install_failed | 安装失败 |

#### 错误码（exit_code）
- `0`: 成功
- `-1`: 未设置或未知错误
- `>0`: 命令退出码
- `127`: 命令未找到

### 6.5 连接管理

#### 心跳机制
- 默认间隔: 30 秒
- 超时: 90 秒（3次心跳未收到）
- 心跳包包含时间戳和运行时间

#### 重连机制
- 默认重连间隔: 5 秒
- 指数退避: 最多 30 秒
- 最大重试次数: 10 次

**重连逻辑:**
```c
delay = min(base_delay * (2 ^ attempt), max_delay)
sleep(delay)
connect()
```

### 6.6 安全性

#### 输入验证
- 路径必须规范化（防止目录遍历）
- 文件名必须转义特殊字符
- 命令参数必须正确转义

**C 代码示例:**
```c
void escape_shell_arg(const char *src, char *dst, size_t dst_size) {
    dst[0] = '\'';
    // ... 转义逻辑 ...
    dst[len] = '\'';
    dst[len + 1] = '\0';
}
```

#### 传输加密
- 当前使用明文 TCP
- 生产环境建议使用 TLS/SSL

---

## 7. 已知问题与建议

### 7.1 未实现功能

#### 1. 断点续传
- `FILE_DOWNLOAD_REQUEST` 支持 `offset` 参数
- Agent 已实现部分逻辑
- 建议完善断点续传功能

#### 2. TLS/SSL 加密
- 当前使用明文 TCP
- 生产环境存在安全风险
- 建议添加 TLS 支持

### 7.2 性能优化建议

#### 1. 消息压缩
- 大文件传输时可启用压缩
- 建议使用 gzip

#### 2. 二进制协议
- JSON 有开销
- 对于高频小消息，可考虑 Protocol Buffers
- 建议：保留 JSON，新增二进制选项

#### 3. 连接池
- Agent 当前是单连接
- Server 可维护连接池
- 建议：保持现状，简单可靠

### 7.3 文档改进

#### 1. 自动生成代码
- 从 PROTOCOL.md 生成代码
- 保持同步
- 工具：使用 JSON Schema 或 OpenAPI

#### 2. 示例代码
- 添加完整的使用示例
- 覆盖所有消息类型
- 建议创建 `examples/` 目录

#### 3. 测试用例
- 自动化协议测试
- 端到端测试
- 建议使用 pytest + pytest-asyncio

---

## 8. 版本历史

| 版本 | 日期 | 作者 | 变更 |
|------|------|------|------|
| 1.1.0 | 2024-02-17 | AI Assistant | 删除未实现的消息类型(0x27, 0x40-0x47)，修复 has_update 为布尔类型，统一字段命名为 snake_case |
| 1.0.0 | 2024-02-16 | AI Assistant | 初始版本，完整协议规范 |

---

## 附录

### A. 快速参考

#### 常用消息类型

| 操作 | 消息类型 | 方向 |
|------|----------|------|
| 心跳 | HEARTBEAT (0x01) | 双向 |
| 系统状态 | SYSTEM_STATUS (0x02) | Agent→Server |
| 创建终端 | PTY_CREATE (0x10) | Server→Agent |
| 终端数据 | PTY_DATA (0x11) | 双向 |
| 文件操作 | FILE_REQUEST (0x20) | Server→Agent |
| 文件数据 | FILE_DATA (0x21) | Agent→Server |
| 文件列表 | FILE_LIST_REQUEST (0x22) | Server→Agent |
| 命令执行 | CMD_REQUEST (0x30) | Server→Agent |
| 命令结果 | CMD_RESPONSE (0x31) | Agent→Server |
| 设备列表 | DEVICE_LIST (0x50) | 双向 |
| 更新检查 | UPDATE_CHECK (0x60) | Agent→Server |

### B. 相关文件

| 组件 | 文件路径 |
|------|----------|
| C Agent | `buildroot-agent/include/agent.h` |
| C Agent | `buildroot-agent/src/agent_protocol.c` |
| Python Server | `buildroot-server/protocol/constants.py` |
| Python Server | `buildroot-server/protocol/models/` |
| Python Server | `buildroot-server/protocol/codec.py` |
| JavaScript Web | `buildroot-web/web_console.html` |
| 构建脚本 | `buildroot-agent/scripts/build.sh` |

### C. 联系方式

- 项目地址: [buildroot-agent GitHub](https://github.com/your-org/buildroot-agent)
- 问题反馈: [Issues](https://github.com/your-org/buildroot-agent/issues)
- 协议讨论: [Discussions](https://github.com/your-org/buildroot-agent/discussions)

---

**文档结束**
