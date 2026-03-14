# Buildroot Agent 通信协议规范

> 版本: 2.0.0
> 最后更新: 2026-03-13
> 状态: 设计版

---

## 目录

- [1. 协议概述](#1-协议概述)
- [2. 双通道架构](#2-双通道架构)
- [3. TCP 协议](#3-tcp-协议)
- [4. MQTT 协议](#4-mqtt-协议)
- [5. Device Twin 模型](#5-device-twin-模型)
- [6. 通信流程](#6-通信流程)
- [7. 认证与授权](#7-认证与授权)
- [8. 实现规范](#8-实现规范)
- [9. 版本历史](#9-版本历史)

---

## 1. 协议概述

### 1.1 设计理念

Buildroot Agent 采用**双通道架构**，TCP 和 MQTT 各司其职，职责清晰，无重叠：

| 原则 | 说明 |
|------|------|
| **低延迟走 TCP** | 需要即时响应的操作（PTY、文件流、命令执行） |
| **状态同步走 MQTT** | 最终一致性即可的操作（Twin、心跳、指标） |
| **职责单一** | 每个通道只做自己擅长的事 |
| **无历史包袱** | 研究项目，直接设计干净的协议 |

### 1.2 通信架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           双通道架构                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│    ┌─────────┐                      ┌─────────┐                    │
│    │         │   TCP (实时控制)     │         │                    │
│    │  Agent  │◄───────────────────►│  Server │◄──── Web ────►     │
│    │         │                      │         │                    │
│    │         │   MQTT (状态同步)    │         │                    │
│    │         │◄───────────────────►│         │                    │
│    └─────────┘                      └─────────┘                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 职责划分

| 通道 | 职责 | 特点 |
|------|------|------|
| **TCP** | PTY 终端、文件传输、命令执行、脚本运行 | 低延迟、双向流式、即时响应 |
| **MQTT** | Device Twin、心跳保活、指标上报、告警通知 | 最终一致性、pub/sub、轻量级 |

---

## 2. 双通道架构

### 2.1 TCP 通道

**定位：实时交互控制通道**

```
┌─────────────────────────────────────────────────────────────┐
│                      TCP 通道                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  • PTY 终端会话                                            │
│    - 交互式 shell                                          │
│    - 实时输入输出                                          │
│    - 毫秒级延迟                                            │
│                                                             │
│  • 文件传输                                                │
│    - 上传/下载文件                                         │
│    - 打包下载目录                                          │
│    - 断点续传支持                                          │
│    - 流式传输大数据                                        │
│                                                             │
│  • 命令执行                                                │
│    - 即时执行 shell 命令                                   │
│    - 获取 stdout/stderr                                    │
│    - 获取退出码                                            │
│                                                             │
│  • 脚本执行                                                │
│    - 下发脚本内容                                          │
│    - 同步执行等待结果                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 MQTT 通道

**定位：状态同步通道**

```
┌─────────────────────────────────────────────────────────────┐
│                      MQTT 通道                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  • Device Twin                                             │
│    - desired: 云端期望状态                                 │
│    - reported: 设备已报告状态                              │
│    - delta: 自动计算差异，设备执行收敛                     │
│                                                             │
│  • 生命周期管理                                            │
│    - 设备上线通知                                          │
│    - 设备离线检测（MQTT 遗嘱）                             │
│    - 心跳保活                                              │
│                                                             │
│  • 监控指标                                                │
│    - 系统指标：CPU/内存/磁盘                               │
│    - 网络指标：流量/连接数                                 │
│    - 自定义指标                                            │
│                                                             │
│  • 告警通知                                                │
│    - 健康告警                                              │
│    - 阈值告警                                              │
│                                                             │
│  • 配置下发                                                │
│    - 通过 Twin desired 下发                                │
│    - 设备订阅执行                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 场景对照表

| 场景 | 通道 | 理由 |
|------|------|------|
| 用户打开终端 | TCP | 实时交互，毫秒级延迟 |
| 用户下载日志文件 | TCP | 流式传输，支持断点续传 |
| 用户执行 shell 命令 | TCP | 需要即时返回结果 |
| 用户运行脚本 | TCP | 同步执行，等待结果 |
| 设备上报 CPU/内存 | MQTT | 定时上报，无需实时 |
| 设备心跳保活 | MQTT | QoS 1 + 遗嘱，自动检测离线 |
| 设备上线/离线 | MQTT | MQTT 遗嘱消息自动处理 |
| 云端下发配置变更 | MQTT | Twin desired 推送 |
| 云端下发固件更新 | MQTT | Twin desired 推送 |
| 设备告警 | MQTT | 异步通知，无需即时响应 |

---

## 3. TCP 协议

### 3.1 消息格式

所有 TCP 消息采用统一的二进制封装格式：

```
+--------+-------------------+------------------------+
| Type   | Length            | JSON Data              |
| (1B)   | (2B, Big Endian)  | (Length bytes)         |
+--------+-------------------+------------------------+
```

**字段说明:**

| 字段 | 大小 | 字节序 | 说明 |
|------|------|--------|------|
| Type | 1 byte | - | 消息类型（0x00-0xFF） |
| Length | 2 bytes | Big Endian | JSON 数据的字节长度 |
| JSON Data | N bytes | - | UTF-8 编码的 JSON 字符串 |

**最大消息大小:** 65535 字节（约 64KB）

### 3.2 消息类型

| 消息类型 | 十六进制 | 名称 | 方向 | 说明 |
|---------|---------|------|------|------|
| **注册** ||||
| REGISTER | 0xF0 | 设备注册 | Agent→Server | TCP 连接后立即发送 |
| REGISTER_RESULT | 0xF1 | 注册结果 | Server→Agent | 返回注册状态 |
| **PTY 终端** ||||
| PTY_CREATE | 0x10 | 创建 PTY | Server→Agent | 创建终端会话 |
| PTY_DATA | 0x11 | PTY 数据 | 双向 | 终端数据传输 |
| PTY_RESIZE | 0x12 | PTY 调整 | Server→Agent | 调整终端大小 |
| PTY_CLOSE | 0x13 | 关闭 PTY | 双向 | 关闭终端会话 |
| **文件传输** ||||
| FILE_REQUEST | 0x20 | 文件请求 | Server→Agent | 文件操作请求 |
| FILE_DATA | 0x21 | 文件数据 | Agent→Server | 文件数据传输 |
| FILE_LIST_REQUEST | 0x22 | 列表请求 | Server→Agent | 请求文件列表 |
| FILE_LIST_RESPONSE | 0x23 | 列表响应 | Agent→Server | 返回文件列表 |
| DOWNLOAD_PACKAGE | 0x24 | 打包下载 | 双向 | 文件打包下载 |
| FILE_DOWNLOAD_REQUEST | 0x25 | 下载请求 | Server→Agent | TCP 下载请求 |
| FILE_DOWNLOAD_DATA | 0x26 | 下载数据 | 双向 | TCP 下载数据 |
| **命令执行** ||||
| CMD_REQUEST | 0x30 | 命令请求 | Server→Agent | 执行命令 |
| CMD_RESPONSE | 0x31 | 命令响应 | Agent→Server | 命令执行结果 |
| **脚本执行** ||||
| SCRIPT_RECV | 0x04 | 接收脚本 | Server→Agent | 下发脚本 |
| SCRIPT_RESULT | 0x05 | 脚本结果 | Agent→Server | 返回执行结果 |
| **设备管理** ||||
| DEVICE_LIST | 0x50 | 设备列表 | 双向 | 设备列表查询 |
| DEVICE_DISCONNECT | 0x51 | 设备断开 | Server→Agent | 设备断开通知 |

### 3.3 消息定义

#### REGISTER (0xF0) - 设备注册

**方向:** Agent → Server

**描述:** 设备 TCP 连接后立即发送，用于注册身份。

**数据结构:**

```json
{
  "device_id": "device-001",
  "version": "2.0.0",
  "mqtt_ready": true
}
```

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| device_id | string | 是 | 设备唯一标识 |
| version | string | 否 | Agent 版本号 |
| mqtt_ready | boolean | 否 | MQTT 是否已连接 |

---

#### PTY_CREATE (0x10) - 创建 PTY 会话

**方向:** Server → Agent

**描述:** 创建交互式终端会话。

```json
{
  "session_id": 1,
  "rows": 24,
  "cols": 80
}
```

| 字段 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| session_id | int | 是 | - | 会话 ID |
| rows | int | 否 | 24 | 终端行数 |
| cols | int | 否 | 80 | 终端列数 |

---

#### PTY_DATA (0x11) - PTY 数据传输

**方向:** 双向

**描述:** 传输终端数据（输入/输出）。

```json
{
  "session_id": 1,
  "data": "bHM="
}
```

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| session_id | int | 是 | 会话 ID |
| data | string | 是 | PTY 数据（base64 编码） |

---

#### PTY_RESIZE (0x12) - PTY 窗口调整

**方向:** Server → Agent

```json
{
  "session_id": 1,
  "rows": 30,
  "cols": 120
}
```

---

#### PTY_CLOSE (0x13) - 关闭 PTY 会话

**方向:** 双向

```json
{
  "session_id": 1,
  "reason": "user_closed"
}
```

---

#### FILE_REQUEST (0x20) - 文件操作请求

**方向:** Server → Agent

**支持的操作:**

| action | 描述 | 响应消息 |
|--------|------|----------|
| upload | 上传文件 | FILE_DATA |
| tail | 读取文件末尾 | FILE_DATA |
| watch | 监控文件 | FILE_DATA (持续) |
| unwatch | 停止监控 | - |
| list | 列出目录 | FILE_LIST_RESPONSE |
| read | 读取文件 | FILE_DATA |
| write | 写入文件 | FILE_DATA |

**示例:**

```json
{
  "action": "upload",
  "filepath": "/var/log/app.log",
  "request_id": "req-123"
}
```

```json
{
  "action": "write",
  "filepath": "/tmp/test.txt",
  "content": "SGVsbG8gV29ybGQ=",
  "mtime": 1708000000000,
  "force": true,
  "request_id": "req-456"
}
```

---

#### FILE_DATA (0x21) - 文件数据

**方向:** Agent → Server

```json
{
  "filepath": "/var/log/app.log",
  "content": "SGVsbG8gV29ybGQ=",
  "size": 11,
  "request_id": "req-123"
}
```

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| filepath | string | 否 | 文件路径 |
| content | string | 否 | 文件内容（base64） |
| size | int | 否 | 文件大小 |
| error | string | 否 | 错误信息 |
| request_id | string | 否 | 请求 ID |

---

#### FILE_LIST_REQUEST (0x22) - 文件列表请求

**方向:** Server → Agent

```json
{
  "path": "/root",
  "request_id": "req-123"
}
```

---

#### FILE_LIST_RESPONSE (0x23) - 文件列表响应

**方向:** Agent → Server

```json
{
  "path": "/root",
  "files": [
    {"name": "file1.txt", "path": "/root/file1.txt", "is_dir": 0, "size": 1024},
    {"name": "docs", "path": "/root/docs", "is_dir": 1, "size": 4096}
  ],
  "chunk": 0,
  "total_chunks": 1,
  "request_id": "req-123"
}
```

**分块策略:** 每个 chunk 最多 20 个文件

---

#### DOWNLOAD_PACKAGE (0x24) - 打包下载

**方向:** 双向

**请求 (Server → Agent):**

```json
{
  "path": "/var/log",
  "format": "tar",
  "request_id": "req-123"
}
```

**响应 (Agent → Server，分块):**

```json
{
  "filename": "archive.tar",
  "size": 1024000,
  "content": "base64data...",
  "chunk_index": 0,
  "total_chunks": 5,
  "request_id": "req-123",
  "complete": false
}
```

---

#### CMD_REQUEST (0x30) - 命令请求

**方向:** Server → Agent

```json
{
  "cmd": "ls -la /root",
  "request_id": "req-123"
}
```

**内置命令:**

| 命令 | 描述 |
|------|------|
| reboot | 重启设备 |
| pty_list | 列出 PTY 会话 |
| script_list | 列出脚本 |
| 其他 | 执行 shell 命令 |

---

#### CMD_RESPONSE (0x31) - 命令响应

**方向:** Agent → Server

```json
{
  "request_id": "req-123",
  "exit_code": 0,
  "success": true,
  "stdout": "file1.txt\nfile2.txt\n",
  "stderr": ""
}
```

---

#### SCRIPT_RECV (0x04) - 接收脚本

**方向:** Server → Agent

```json
{
  "script_id": "script-001",
  "content": "#!/bin/bash\necho 'Hello World'",
  "execute": true
}
```

---

#### SCRIPT_RESULT (0x05) - 脚本执行结果

**方向:** Agent → Server

```json
{
  "script_id": "script-001",
  "exit_code": 0,
  "success": true,
  "output": "Hello World\n"
}
```

---

## 4. MQTT 协议

### 4.1 消息格式

所有 MQTT 消息采用统一的 JSON 格式：

```json
{
  "$version": 42,
  "$timestamp": 1708000000000,
  "payload": {
    // 实际数据
  }
}
```

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| $version | int | 是 | 消息版本号（递增） |
| $timestamp | int64 | 是 | 时间戳（毫秒） |
| payload | object | 是 | 实际数据负载 |

### 4.2 Topic 设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Topic 层次结构                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  twin/{device_id}/desired       Server → Agent              │
│  twin/{device_id}/reported      Agent → Server              │
│                                                             │
│  status/{device_id}/online      Agent → Server (retain)     │
│  status/{device_id}/offline     MQTT 遗嘱                   │
│  status/{device_id}/heartbeat   Agent → Server              │
│                                                             │
│  metrics/{device_id}/system     Agent → Server              │
│  metrics/{device_id}/network    Agent → Server              │
│  metrics/{device_id}/custom     Agent → Server              │
│                                                             │
│  alert/{device_id}/health       Agent → Server              │
│  alert/{device_id}/threshold    Agent → Server              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Device Twin Topics

#### twin/{device_id}/desired

**方向:** Server → Agent

**描述:** 云端下发的期望状态。设备订阅此 topic，收到消息后计算 delta 并执行。

```json
{
  "$version": 42,
  "$timestamp": 1708000000000,
  "payload": {
    "firmware": {
      "version": "2.0.0",
      "url": "https://example.com/firmware-2.0.0.tar"
    },
    "config": {
      "interval": 60,
      "logLevel": "debug"
    }
  }
}
```

---

#### twin/{device_id}/reported

**方向:** Agent → Server

**描述:** 设备上报的已报告状态。设备定期或状态变更时发布。

```json
{
  "$version": 42,
  "$timestamp": 1708000000000,
  "payload": {
    "firmware": {
      "version": "1.0.0"
    },
    "config": {
      "interval": 60,
      "logLevel": "info"
    },
    "system": {
      "cpu_usage": 45.2,
      "mem_used": 2048,
      "mem_total": 4096
    }
  }
}
```

---

### 4.4 生命周期 Topics

#### status/{device_id}/online

**方向:** Agent → Server

**描述:** 设备上线通知。设置为 retain 消息，新订阅者可立即获取。

```json
{
  "$version": 1,
  "$timestamp": 1708000000000,
  "payload": {
    "version": "2.0.0",
    "ip": "192.168.1.100"
  }
}
```

---

#### status/{device_id}/offline

**方向:** MQTT 遗嘱

**描述:** 设备离线通知。通过 MQTT Last Will 机制自动触发。

```json
{
  "$version": 1,
  "$timestamp": 1708000000000,
  "payload": {
    "reason": "connection_lost"
  }
}
```

**遗嘱配置:**

```c
// MQTT 连接时设置遗嘱
mqtt_set_will(client, 
  "status/device-001/offline",
  "{\"$version\":1,\"payload\":{\"reason\":\"connection_lost\"}}",
  QOS_1,
  true  // retain
);
```

---

#### status/{device_id}/heartbeat

**方向:** Agent → Server

**描述:** 心跳保活。设备定期发布，Server 检测超时则标记离线。

```json
{
  "$version": 1,
  "$timestamp": 1708000000000,
  "payload": {
    "uptime": 3600
  }
}
```

**心跳参数:**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 间隔 | 30 秒 | 心跳发布间隔 |
| 超时 | 90 秒 | 3 次心跳未收到则离线 |
| QoS | 1 | 至少一次投递 |

---

### 4.5 监控指标 Topics

#### metrics/{device_id}/system

**方向:** Agent → Server

**描述:** 系统指标上报。

```json
{
  "$version": 1,
  "$timestamp": 1708000000000,
  "payload": {
    "cpu_usage": 45.2,
    "cpu_cores": 4,
    "mem_total": 4096,
    "mem_used": 2048,
    "mem_free": 2048,
    "disk_total": 102400,
    "disk_used": 51200,
    "load_1min": 1.2,
    "load_5min": 1.5,
    "load_15min": 1.3,
    "uptime": 3600
  }
}
```

---

#### metrics/{device_id}/network

**方向:** Agent → Server

**描述:** 网络指标上报。

```json
{
  "$version": 1,
  "$timestamp": 1708000000000,
  "payload": {
    "rx_bytes": 1048576,
    "tx_bytes": 524288,
    "rx_packets": 1000,
    "tx_packets": 500
  }
}
```

---

#### metrics/{device_id}/custom

**方向:** Agent → Server

**描述:** 自定义指标上报。

```json
{
  "$version": 1,
  "$timestamp": 1708000000000,
  "payload": {
    "temperature": 65.5,
    "humidity": 45.0,
    "sensors": [
      {"id": "sensor-1", "value": 23.5},
      {"id": "sensor-2", "value": 24.1}
    ]
  }
}
```

---

### 4.6 告警 Topics

#### alert/{device_id}/health

**方向:** Agent → Server

**描述:** 健康告警。

```json
{
  "$version": 1,
  "$timestamp": 1708000000000,
  "payload": {
    "level": "warning",
    "type": "disk_full",
    "message": "磁盘使用率超过 90%",
    "details": {
      "disk_used": 92160,
      "disk_total": 102400,
      "usage_percent": 90.0
    }
  }
}
```

**告警级别:**

| level | 说明 |
|-------|------|
| info | 信息 |
| warning | 警告 |
| critical | 严重 |
| emergency | 紧急 |

**告警类型:**

| type | 说明 |
|------|------|
| disk_full | 磁盘空间不足 |
| memory_low | 内存不足 |
| cpu_high | CPU 使用率过高 |
| temperature_high | 温度过高 |
| service_down | 服务异常 |
| custom | 自定义告警 |

---

#### alert/{device_id}/threshold

**方向:** Agent → Server

**描述:** 阈值告警（超过预设阈值触发）。

```json
{
  "$version": 1,
  "$timestamp": 1708000000000,
  "payload": {
    "level": "critical",
    "metric": "cpu_usage",
    "value": 95.5,
    "threshold": 90.0,
    "message": "CPU 使用率超过阈值"
  }
}
```

---

## 5. Device Twin 模型

### 5.1 状态模型

Device Twin 采用 desired/reported/delta 三态模型：

```
┌─────────────────────────────────────────────────────────────┐
│                    Device Twin                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  desired (云端期望)                                         │
│  ├── 由云端/用户设置                                        │
│  ├── 发布到 twin/{id}/desired                               │
│  └── 设备订阅执行                                           │
│                                                             │
│  reported (设备上报)                                        │
│  ├── 设备实际状态                                           │
│  ├── 发布到 twin/{id}/reported                              │
│  └── 云端订阅存储                                           │
│                                                             │
│  delta (自动计算)                                           │
│  ├── desired ∩ reported 的差异                              │
│  ├── 设备本地计算                                           │
│  └── 执行后收敛到 reported                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 状态示例

**云端期望 (desired):**

```json
{
  "$version": 42,
  "payload": {
    "firmware": { "version": "2.0.0" },
    "config": { "interval": 60, "logLevel": "debug" }
  }
}
```

**设备上报 (reported):**

```json
{
  "$version": 41,
  "payload": {
    "firmware": { "version": "1.0.0" },
    "config": { "interval": 60, "logLevel": "info" }
  }
}
```

**差异 (delta):**

```json
{
  "firmware": { "version": "2.0.0" },
  "config": { "logLevel": "debug" }
}
```

**说明:**
- `config.interval` 两边都是 60，无差异
- `firmware.version` 需要更新到 2.0.0
- `config.logLevel` 需要更新到 debug

### 5.3 版本控制

- 每条消息携带 `$version`，单调递增
- 设备忽略 `$version` 小于等于当前版本的消息
- 防止乱序、重复消息导致的错误执行

```c
// 设备端版本检查
if (msg_version > current_version) {
  current_version = msg_version;
  execute_delta(msg);
}
```

### 5.4 同步状态

| 状态 | 说明 |
|------|------|
| synced | reported == desired，无差异 |
| syncing | 正在执行 delta，尚未上报 |
| failed | delta 执行失败 |

---

## 6. 通信流程

### 6.1 设备连接流程

```
┌──────────┐                              ┌──────────┐
│  Agent   │                              │  Server  │
└────┬─────┘                              └────┬─────┘
     │                                         │
     │  ========== TCP 连接 ==========         │
     │                                         │
     │── TCP Socket 连接 ─────────────────────►│
     │                                         │
     │── REGISTER (0xF0) ─────────────────────►│
     │   {device_id, version}                  │
     │                                         │
     │◄── REGISTER_RESULT (0xF1) ─────────────│
     │   {success: true}                       │
     │                                         │
     │  ========== MQTT 连接 ==========         │
     │                                         │
     │── MQTT Connect ────────────────────────►│
     │   username: {device_id}                 │
     │   password: <凭证>                      │
     │   clean_session: true                   │
     │   will: status/{id}/offline             │
     │                                         │
     │── sub twin/{id}/desired ───────────────►│
     │                                         │
     │── pub status/{id}/online (retain) ─────►│
     │   {version, timestamp}                  │
     │                                         │
     │── pub twin/{id}/reported ──────────────►│
     │   {当前状态}                            │
     │                                         │
     │  ========== 双通道就绪 ==========        │
     │                                         │
     │── pub status/{id}/heartbeat (定时) ────►│
     │── pub metrics/{id}/system (定时) ──────►│
```

### 6.2 Device Twin 同步流程

```
┌──────────┐          ┌──────────┐          ┌──────────┐
│  Agent   │          │  Server  │          │   Web    │
└────┬─────┘          └────┬─────┘          └────┬─────┘
     │                     │                      │
     │                     │                      │
     │  [初始状态]         │                      │
     │                     │                      │
     │  pub twin/{id}/reported                   │
     │────────────────────►│── 存 DB/缓存 ───────►│
     │  {firmware: 1.0.0}  │                      │
     │                     │                      │
     │                     │                      │
     │                     │  用户设置 desired   │
     │                     │◄─────────────────────│
     │                     │  PATCH /twin        │
     │                     │                      │
     │                     │                      │
     │  pub twin/{id}/desired                    │
     │◄────────────────────│                      │
     │  {firmware: 2.0.0}  │                      │
     │  $version: 42       │                      │
     │                     │                      │
     │                     │                      │
     │  [计算 delta]       │                      │
     │  delta = {firmware: 2.0.0}                │
     │                     │                      │
     │                     │                      │
     │  [执行 delta]       │                      │
     │  下载固件...        │                      │
     │  安装固件...        │                      │
     │                     │                      │
     │                     │                      │
     │  pub twin/{id}/reported                   │
     │────────────────────►│── 更新 DB ──────────►│
     │  {firmware: 2.0.0}  │                      │
     │  $version: 43       │                      │
     │                     │                      │
     │                     │                      │
     │  [同步完成]         │                      │
     │                     │                      │
```

### 6.3 PTY 终端流程

```
┌──────────┐          ┌──────────┐          ┌──────────┐
│  Agent   │          │  Server  │          │   Web    │
└────┬─────┘          └────┬─────┘          └────┬─────┘
     │                     │                      │
     │                     │                      │
     │                     │  用户打开终端       │
     │                     │◄─────────────────────│
     │                     │                      │
     │                     │                      │
     │  PTY_CREATE (0x10)  │                      │
     │◄────────────────────│                      │
     │  {session_id: 1}    │                      │
     │                     │                      │
     │                     │                      │
     │  [创建 PTY]         │                      │
     │                     │                      │
     │                     │                      │
     │  PTY_DATA (0x11)    │                      │
     │────────────────────►│─────────────────────►│
     │  {data: "shell$ "}  │                      │
     │                     │                      │
     │                     │                      │
     │                     │  用户输入 "ls"      │
     │                     │◄─────────────────────│
     │                     │                      │
     │                     │                      │
     │  PTY_DATA (0x11)    │                      │
     │◄────────────────────│                      │
     │  {data: "bHM="}     │                      │
     │                     │                      │
     │                     │                      │
     │  [执行命令]         │                      │
     │                     │                      │
     │                     │                      │
     │  PTY_DATA (0x11)    │                      │
     │────────────────────►│─────────────────────►│
     │  {data: "file1..."} │                      │
     │                     │                      │
     │                     │                      │
     │  PTY_CLOSE (0x13)   │                      │
     │◄────────────────────│                      │
     │  {session_id: 1}    │                      │
     │                     │                      │
```

### 6.4 文件下载流程

```
┌──────────┐          ┌──────────┐          ┌──────────┐
│  Agent   │          │  Server  │          │   Web    │
└────┬─────┘          └────┬─────┘          └────┬─────┘
     │                     │                      │
     │                     │  用户下载日志       │
     │                     │◄─────────────────────│
     │                     │                      │
     │                     │                      │
     │  FILE_REQUEST (0x20)│                      │
     │◄────────────────────│                      │
     │  {action: "upload", │                      │
     │   filepath: "..."}  │                      │
     │                     │                      │
     │                     │                      │
     │  [读取文件]         │                      │
     │                     │                      │
     │                     │                      │
     │  FILE_DATA (0x21)   │                      │
     │────────────────────►│─────────────────────►│
     │  {content: "...",   │                      │
     │   size: 1024}       │                      │
     │                     │                      │
```

---

## 7. 认证与授权

### 7.1 MQTT 认证

设备使用 EMQX 内置数据库认证：

| 字段 | 说明 |
|------|------|
| username | device_id |
| password | 设备凭证（注册时生成） |
| is_superuser | false |

### 7.2 MQTT 授权 (ACL)

每个设备只能访问自己的 topic：

```erlang
% 设备 ACL 规则
{allow, {username, "%u"}, publish, ["twin/%u/reported"]}.
{allow, {username, "%u"}, publish, ["status/%u/#"]}.
{allow, {username, "%u"}, publish, ["metrics/%u/#"]}.
{allow, {username, "%u"}, publish, ["alert/%u/#"]}.

{allow, {username, "%u"}, subscribe, ["twin/%u/desired"]}.

% Server 超级用户
{allow, {username, "twin-server"}, publish, ["twin/+/desired"]}.
{allow, {username, "twin-server"}, subscribe, ["twin/+/reported"]}.
{allow, {username, "twin-server"}, subscribe, ["status/+/offline"]}.
{allow, {username, "twin-server"}, subscribe, ["metrics/+/#"]}.
{allow, {username, "twin-server"}, subscribe, ["alert/+/#"]}.

% 默认拒绝
{deny, all}.
```

### 7.3 TCP 认证

TCP 通道目前采用注册模式（无密码），依赖 MQTT 凭证：

1. 设备 TCP 连接
2. 发送 REGISTER（包含 device_id）
3. Server 验证 MQTT 凭证（设备需先通过 MQTT 认证）
4. 验证通过则建立 TCP 会话

**未来扩展:** 可添加 token 认证

---

## 8. 实现规范

### 8.1 命名规范

- **Topic:** snake_case（`twin/device_id/desired`）
- **JSON 字段:** snake_case（`device_id`, `session_id`）
- **消息类型:** 大写下划线（`PTY_CREATE`, `FILE_DATA`）

### 8.2 时间戳

- 使用 Unix 时间戳（毫秒）
- 类型: `int64`
- 时区: UTC

### 8.3 Base64 编码

- 文件内容、PTY 数据使用标准 Base64 编码
- 不使用 URL 安全字符

### 8.4 错误处理

**TCP 错误响应:**

```json
{
  "error": "file_not_found",
  "message": "文件不存在",
  "request_id": "req-123"
}
```

**常见错误码:**

| error | 说明 |
|-------|------|
| file_not_found | 文件不存在 |
| permission_denied | 权限不足 |
| invalid_request | 无效请求 |
| timeout | 超时 |

### 8.5 连接参数

| 参数 | TCP | MQTT |
|------|-----|------|
| 心跳间隔 | - | 30 秒 |
| 连接超时 | 10 秒 | 10 秒 |
| 重连间隔 | 5 秒 | 5 秒 |
| 最大重连次数 | 10 | 无限 |

---

## 9. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 2.0.0 | 2026-03-13 | 双通道架构重设计：TCP 专注实时控制，MQTT 专注状态同步；移除 TCP 心跳/状态上报；新增 Device Twin 模型、MQTT Topic 设计 |
| 1.4.0 | 2025-02-27 | 系统状态不再广播给 Web |
| 1.3.0 | 2024-02-17 | 重构更新流程 |
| 1.0.0 | 2024-02-16 | 初始版本 |

---

## 附录

### A. 快速参考

**TCP 消息类型:**

| 操作 | 消息 | 方向 |
|------|------|------|
| 注册 | REGISTER (0xF0) | Agent→Server |
| 终端 | PTY_* (0x10-0x13) | 双向 |
| 文件 | FILE_* (0x20-0x27) | 双向 |
| 命令 | CMD_* (0x30-0x31) | 双向 |
| 脚本 | SCRIPT_* (0x04-0x05) | 双向 |

**MQTT Topics:**

| Topic | 方向 | 用途 |
|-------|------|------|
| twin/{id}/desired | Server→Agent | 期望状态 |
| twin/{id}/reported | Agent→Server | 已报告状态 |
| status/{id}/online | Agent→Server | 上线通知 |
| status/{id}/offline | 遗嘱 | 离线通知 |
| status/{id}/heartbeat | Agent→Server | 心跳 |
| metrics/{id}/system | Agent→Server | 系统指标 |
| alert/{id}/health | Agent→Server | 健康告警 |

### B. 相关文件

| 组件 | 路径 |
|------|------|
| Agent C | buildroot-agent/ |
| Server (Rust) | buildroot-server-rs/ |
| 模拟器 | buildroot-simulator/ |
| 基础设施 | buildroot-infra/ |
| 设计文档 | docs/device-twin-design.md |

---

**文档结束**