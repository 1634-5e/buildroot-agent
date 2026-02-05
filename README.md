# Buildroot Agent

嵌入式设备远程管理Agent，专为Buildroot环境设计。

## 功能特性

- ✅ **系统状态采集** - CPU、内存、磁盘、网络、负载等
- ✅ **日志上报** - 文件上传、tail跟踪、实时监控
- ✅ **脚本下发执行** - 接收并执行云端下发的脚本
- ✅ **交互式Shell (PTY)** - 远程终端，支持窗口大小调整
- ✅ **安全通信** - 仅作为客户端主动连接，不暴露任何端口
- ✅ **断线重连** - 自动重连机制
- ✅ **守护进程** - 支持后台运行

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    Cloud Server                          │
│                  (WebSocket Server)                       │
└─────────────────────────┬───────────────────────────────┘
                          │ WSS (TLS加密)
                          │ 仅Agent主动连接
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   Buildroot Agent                         │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 状态采集 │ │ 日志上报 │ │ 脚本执行 │ │   PTY    │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘   │
│       └────────────┴────────────┴────────────┘          │
│                         │                                │
│              ┌──────────┴──────────┐                    │
│              │   WebSocket Client  │                    │
│              │   (libwebsockets)   │                    │
│              └─────────────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

## 目录结构

```
buildroot-agent/
├── include/
│   └── agent.h              # 主头文件
├── src/
│   ├── agent_main.c         # 主程序
│   ├── agent_websocket.c    # WebSocket客户端
│   ├── agent_status.c       # 系统状态采集
│   ├── agent_log.c          # 日志上报
│   ├── agent_script.c       # 脚本执行
│   ├── agent_pty.c          # 交互式Shell
│   ├── agent_protocol.c     # 协议处理
│   ├── agent_config.c       # 配置管理
│   └── agent_util.c         # 工具函数
├── scripts/
│   ├── S99agent             # init.d启动脚本
│   └── agent.conf.sample    # 配置文件示例
├── buildroot-package/
│   └── buildroot-agent/
│       ├── Config.in        # Buildroot菜单配置
│       └── buildroot-agent.mk # Buildroot编译规则
├── Makefile                 # 编译脚本
└── README.md                # 说明文档
```

## 编译

### 本地编译 (测试用)

```bash
# 安装依赖 (Ubuntu/Debian)
sudo apt-get install libwebsockets-dev libssl-dev

# 编译
make

# 调试模式编译
make DEBUG=1

# 运行
./bin/buildroot-agent -v
```

### 交叉编译 (嵌入式目标)

```bash
# ARM目标
make CC=arm-linux-gnueabihf-gcc STRIP=arm-linux-gnueabihf-strip

# MIPS目标
make CC=mips-linux-gnu-gcc STRIP=mips-linux-gnu-strip
```

### Buildroot集成

1. 复制package到Buildroot:
```bash
cp -r buildroot-package/buildroot-agent /path/to/buildroot/package/
```

2. 添加到package菜单:
```bash
# 编辑 package/Config.in，添加:
source "package/buildroot-agent/Config.in"
```

3. 配置并编译:
```bash
make menuconfig  # 选择 buildroot-agent
make
```

## 配置

配置文件路径: `/etc/agent/agent.conf`

```ini
# 服务器地址
server_url = "wss://your-server.com/agent"

# 认证Token
auth_token = "your-auth-token"

# 心跳间隔 (秒)
heartbeat_interval = 30

# 状态上报间隔 (秒)
status_interval = 60

# 启用PTY
enable_pty = true

# 启用脚本执行
enable_script = true
```

## 运行

```bash
# 前台运行 (调试)
buildroot-agent -c /etc/agent/agent.conf -v

# 守护进程运行
buildroot-agent -c /etc/agent/agent.conf -d

# 生成默认配置
buildroot-agent -g -c /etc/agent/agent.conf

# 查看帮助
buildroot-agent -h
```

## 通信协议

### 消息格式

```
| 类型 (1 byte) | JSON数据 |
```

### 消息类型

| 类型 | 值 | 方向 | 说明 |
|------|-----|------|------|
| HEARTBEAT | 0x01 | 双向 | 心跳 |
| SYSTEM_STATUS | 0x02 | Agent→Server | 系统状态 |
| LOG_UPLOAD | 0x03 | Agent→Server | 日志上传 |
| SCRIPT_RECV | 0x04 | Server→Agent | 接收脚本 |
| SCRIPT_RESULT | 0x05 | Agent→Server | 脚本执行结果 |
| PTY_CREATE | 0x10 | Server→Agent | 创建PTY |
| PTY_DATA | 0x11 | 双向 | PTY数据 |
| PTY_RESIZE | 0x12 | Server→Agent | 调整窗口 |
| PTY_CLOSE | 0x13 | 双向 | 关闭PTY |
| AUTH | 0xF0 | Agent→Server | 认证请求 |
| AUTH_RESULT | 0xF1 | Server→Agent | 认证结果 |

### 示例消息

**认证请求:**
```json
{
  "device_id": "abc123",
  "token": "auth-token",
  "version": "1.0.0",
  "timestamp": 1699999999999
}
```

**系统状态:**
```json
{
  "cpu_usage": 25.5,
  "mem_total": 512.0,
  "mem_used": 256.0,
  "load_1min": 0.5,
  "uptime": 86400,
  "ip_addr": "192.168.1.100",
  "hostname": "device-001"
}
```

**创建PTY:**
```json
{
  "session_id": 1,
  "rows": 24,
  "cols": 80
}
```

## 安全考虑

1. **无监听端口** - Agent仅作为客户端主动连接服务器
2. **TLS加密** - 使用WSS协议加密通信
3. **Token认证** - 设备需要有效Token才能连接
4. **权限控制** - PTY和脚本执行可独立启用/禁用
5. **路径安全** - 脚本名防止路径遍历攻击

## 依赖

- libwebsockets >= 3.0
- OpenSSL >= 1.1
- pthread

## License

MIT License
