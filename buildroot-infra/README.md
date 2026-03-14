# Buildroot Agent 基础设施

用于 Device Twin 改造的开发环境，包含 EMQX、PostgreSQL、Redis。

## 快速开始

### 1. 启动环境

```bash
cd buildroot-infra
./scripts/dev-up.sh
```

启动后：
- **EMQX Dashboard**: http://localhost:18083 (admin / buildroot123)
- **内置 WebSocket 工具**: Dashboard → 工具 → WebSocket 客户端

### 2. 验证服务

```bash
# EMQX Dashboard
open http://localhost:18083
# 用户名: admin
# 密码: buildroot123

# PostgreSQL
psql -h localhost -U buildroot -d buildroot_agent

# Redis
redis-cli -h localhost -p 6379 -a buildroot123
```

### 3. MQTT 测试

**安装 MQTTX CLI**

```bash
# macOS
brew install mqttx-cli

# Linux (x64)
curl -fsSL https://github.com/emqx/MQTTX/releases/latest/download/mqttx-cli-linux-x64 -o /usr/local/bin/mqttx
chmod +x /usr/local/bin/mqttx

# Windows (Scoop)
scoop install mqttx-cli

# 或使用 npm
npm install -g mqttx-cli
```

**测试命令**

```bash
# 订阅所有 twin 消息
mqttx sub -h localhost -p 1883 -t 'twin/#' -v

# 发布测试消息
mqttx pub -h localhost -p 1883 -t 'twin/test-device/desired' -m '{"$version":1,"data":{"config":{"rate":1000}}}'

# 或者使用 EMQX Dashboard 内置的 WebSocket 工具
# http://localhost:18083 → 工具 → WebSocket 客户端
```

## 服务地址

| 服务 | 地址 | 说明 |
|------|------|------|
| EMQX Dashboard | http://localhost:18083 | 管理界面 |
| MQTT | mqtt://localhost:1883 | MQTT 协议 |
| MQTT/TLS | mqtts://localhost:8883 | MQTT over TLS |
| WebSocket | ws://localhost:8083/mqtt | WebSocket 连接 |
| PostgreSQL | localhost:5432 | 数据库 |
| Redis | localhost:6379 | 缓存 |

## 目录结构

```
buildroot-infra/
├── docker-compose.yml    # Docker Compose 配置
├── .env.example          # 环境变量示例
├── emqx/
│   └── emqx.conf         # EMQX 配置
├── postgres/
│   └── init/
│       └── 001_twin_tables.sql  # 数据库初始化
├── redis/
└── scripts/
    ├── dev-up.sh         # 启动环境
    ├── dev-down.sh       # 停止环境
    └── dev-reset.sh      # 重置数据
```

## 数据库结构

### device_twins 表

| 字段 | 类型 | 说明 |
|------|------|------|
| device_id | VARCHAR(64) | 设备 ID (主键) |
| desired | JSONB | 期望状态 |
| desired_version | BIGINT | 期望状态版本 |
| reported | JSONB | 已报告状态 |
| reported_version | BIGINT | 已报告状态版本 |
| tags | JSONB | 标签 |

### 查询示例

```sql
-- 查看所有设备
SELECT device_id, desired_version, reported_version FROM device_twins;

-- 查看设备详情
SELECT * FROM device_twins WHERE device_id = 'HTCU-DEV-001';

-- 计算差异
SELECT device_id, compute_twin_delta(device_id) AS delta FROM device_twins;

-- 查看设备概览（含同步状态）
SELECT * FROM v_device_overview;
```

## MQTT Topic 设计

```
twin/{device_id}/desired     # 云端 → 设备（期望状态）
twin/{device_id}/reported    # 设备 → 云端（已报告状态）
twin/{device_id}/cmd         # 设备 → 云端（命令请求）
twin/{device_id}/ack         # 云端 → 设备（确认响应）
```

### 消息格式

**Desired (云端 → 设备)**

```json
{
  "$version": 5,
  "$timestamp": "2026-03-11T12:00:00Z",
  "data": {
    "firmware": {"version": "2.1.0"},
    "config": {"sampleRate": 1000}
  }
}
```

**Reported (设备 → 云端)**

```json
{
  "$version": 5,
  "$timestamp": "2026-03-11T12:30:00Z",
  "data": {
    "firmware": {"version": "2.1.0"},
    "config": {"sampleRate": 1000},
    "system": {"cpuUsage": 23.5}
  }
}
```

## 常用操作

### 停止环境

```bash
./scripts/dev-down.sh
```

### 重置数据

```bash
./scripts/dev-reset.sh
```

### 查看日志

```bash
# EMQX 日志
docker logs buildroot-emqx -f

# PostgreSQL 日志
docker logs buildroot-postgres -f

# Redis 日志
docker logs buildroot-redis -f
```

### 进入容器

```bash
# EMQX
docker exec -it buildroot-emqx /bin/sh

# PostgreSQL
docker exec -it buildroot-postgres /bin/bash

# Redis
docker exec -it buildroot-redis /bin/sh
```

## 生产环境注意事项

1. **修改默认密码** - 修改 `.env` 中的所有密码
2. **配置 TLS** - 使用正式 SSL 证书
3. **配置 ACL** - 限制设备只能访问自己的 topic
4. **数据备份** - 配置 PostgreSQL 定期备份
5. **监控告警** - 接入 Prometheus/Grafana

## 下一步

1. 完成 Phase 1 后，进入 Phase 2：Agent 端开发
2. 参考 `docs/device-twin-design.md` 实现细节
3. 参考 `docs/device-twin-tasks.md` 任务列表