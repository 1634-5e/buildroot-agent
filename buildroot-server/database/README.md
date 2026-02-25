# Buildroot Agent Server - Database Integration Guide

## 概述

本文档说明如何为 buildroot-agent server 配置和使用 PostgreSQL 数据库，实现长期、大规模的数据存储。

## 快速开始

### 1. 安装 PostgreSQL

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# macOS (使用 Homebrew)
brew install postgresql

# 启动 PostgreSQL 服务
sudo service postgresql start  # Linux
brew services start postgresql  # macOS
```

### 2. 创建数据库

```bash
# 切换到 postgres 用户
sudo -u postgres psql

# 在 psql 中执行以下命令
CREATE DATABASE buildroot_agent;
CREATE USER buildroot WITH PASSWORD 'buildroot';
GRANT ALL PRIVILEGES ON DATABASE buildroot_agent TO buildroot;
\q
```

### 3. 安装 Python 依赖

```bash
cd buildroot-server
pip install asyncpg
```

### 4. 初始化数据库表结构

```bash
psql -U buildroot -d buildroot_agent -f database/schema.sql
```

### 5. 配置环境变量（可选）

创建 `.env` 文件或设置环境变量：

```bash
# Database configuration
BR_SERVER_DB_HOST=localhost
BR_SERVER_DB_PORT=5432
BR_SERVER_DB_USER=buildroot
BR_SERVER_DB_PASSWORD=buildroot
BR_SERVER_DB_NAME=buildroot_agent
BR_SERVER_DB_POOL_MIN=5
BR_SERVER_DB_POOL_MAX=20
```

### 6. 启动服务器

```bash
python main.py
```

服务器启动时会自动初始化数据库连接池。

## 数据库架构

### 核心表

| 表名 | 用途 | 分区 |
|------|------|------|
| `devices` | 设备基本信息和当前状态 | 否 |
| `device_status_history` | 设备状态历史（CPU/内存/磁盘等） | 是（按月） |
| `command_history` | 命令执行历史 | 否 |
| `script_history` | 脚本执行历史 | 否 |
| `file_transfers` | 文件传输记录 | 否 |
| `update_history` | Agent更新历史 | 否 |
| `update_approvals` | 更新批准记录 | 否 |
| `web_console_sessions` | Web控制台会话 | 否 |
| `pty_sessions` | PTY终端会话 | 否 |
| `audit_logs` | 审计日志 | 是（按月） |

### 数据保留策略

- `device_status_history`: 保留 90 天
- `audit_logs`: 保留 180 天
- 分区表: 保留最近 3 个月的分区

## 使用示例

### 基本设备操作

```python
from database.repositories import DeviceRepository

# 获取设备
device = await DeviceRepository.get_by_device_id("device-001")

# 创建或更新设备
device = await DeviceRepository.create_or_update(
    device_id="device-001",
    name="My Device",
    version="1.2.3",
    hostname="device-host",
    ip_addr="192.168.1.100",
    tags=["production", "web-server"],
)

# 更新连接状态
await DeviceRepository.update_connection_status(
    device_id="device-001",
    status="online",
    is_online=True,
    last_seen_at=datetime.now(),
)

# 列出设备
devices = await DeviceRepository.list_devices(
    status="online",
    tags=["production"],
    limit=100,
)
```

### 保存设备状态历史

```python
from database.repositories import DeviceStatusHistoryRepository

await DeviceStatusHistoryRepository.insert(
    device_id="device-001",
    cpu_usage=45.2,
    cpu_cores=4,
    cpu_user=30.5,
    cpu_system=14.7,
    mem_total=4096.0,
    mem_used=2048.0,
    mem_free=2048.0,
    disk_total=102400.0,
    disk_used=51200.0,
    load_1min=1.2,
    load_5min=1.5,
    load_15min=1.3,
    uptime=3600,
    net_rx_bytes=1048576,
    net_tx_bytes=524288,
    raw_data={"timestamp": 1234567890},
)
```

### 命令执行历史

```python
from database.repositories import CommandHistoryRepository

# 记录命令执行
result = await CommandHistoryRepository.insert(
    device_id="device-001",
    command="ls -la",
    console_id="console-001",
    request_id="req-123456",
)

# 更新命令结果
await CommandHistoryRepository.update_result(
    request_id="req-123456",
    status="completed",
    exit_code=0,
    success=True,
    stdout="file1.txt\nfile2.txt\n",
)

# 查询命令历史
history = await CommandHistoryRepository.list_by_device(
    device_id="device-001",
    status="completed",
    limit=50,
)
```

### 审计日志

```python
from database.repositories import AuditLogRepository

await AuditLogRepository.insert(
    event_type="device_connect",
    action="connect",
    actor_type="device",
    actor_id="device-001",
    device_id="device-001",
    resource_type="device",
    resource_id="device-001",
    status="success",
    details={"ip_address": "192.168.1.100"},
)
```

## 数据库维护

### 运行维护脚本

```bash
# 创建分区、清理旧数据、运行 VACUUM ANALYZE
python scripts/db_maintenance.py
```

维护脚本会自动执行以下操作：

1. **创建未来3个月的分区** - 为 `device_status_history` 和 `audit_logs` 表
2. **删除旧分区** - 保留最近3个月，删除更早的分区
3. **清理旧数据** - 删除90天前的设备状态历史和180天前的审计日志
4. **运行 VACUUM ANALYZE** - 优化查询性能


### 定时任务（可选）

使用 cron 或 systemd timer 定期运行维护脚本：

```bash
# 每天凌晨2点运行
0 2 * * * cd /path/to/buildroot-server && python scripts/db_maintenance.py
```


## 性能优化建议

### 索引

数据库已包含以下索引：

- 主键索引
- 外键索引
- 频繁查询字段的索引（device_id, status, request_id 等）
- 全文搜索索引（命令搜索）
- GIN 索引（tags 数组）

### 连接池配置

根据实际负载调整连接池大小：

```python
# config/settings.py
db_pool_min: int = Field(default=10)  # 低负载可减少到 5
db_pool_max: int = Field(default=50)  # 高负载可增加到 50+
```

### 查询优化

1. 使用索引字段进行过滤
2. 避免 `SELECT *`，只查询需要的列
3. 使用 `LIMIT` 限制返回结果数
4. 对时序数据使用分区裁剪

## 备份与恢复

### 备份数据库

```bash
# 完整备份
pg_dump -U buildroot -h localhost -d buildroot_agent > backup_$(date +%Y%m%d).sql

# 仅备份表结构
pg_dump -U buildroot -h localhost -d buildroot_agent --schema-only > schema_backup.sql

# 仅备份特定表
pg_dump -U buildroot -h localhost -d buildroot_agent -t devices > devices_backup.sql
```

### 恢复数据库

```bash
# 恢复完整备份
psql -U buildroot -h localhost -d buildroot_agent < backup_20240224.sql

# 恢复特定表
psql -U buildroot -h localhost -d buildroot_agent < devices_backup.sql
```

### 使用 pgAdmin 或其他 GUI 工具

1. 连接到 PostgreSQL 服务器
2. 选择 `buildroot_agent` 数据库
3. 使用工具的备份/恢复功能

## 故障排查

### 连接问题

```bash
# 检查 PostgreSQL 服务状态
sudo service postgresql status

# 检查 PostgreSQL 日志
sudo tail -f /var/log/postgresql/postgresql-*.log
```

### 性能问题

```sql
-- 查看慢查询
SELECT * FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- 查看表大小
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### 连接池问题

如果遇到连接池耗尽：

1. 增加 `db_pool_max` 配置
2. 检查是否有连接泄漏
3. 使用 `pg_stat_activity` 查看活动连接：

```sql
SELECT * FROM pg_stat_activity
WHERE datname = 'buildroot_agent';
```

## 高级功能

### 使用事务

```python
from database.db_manager import db_manager

async with db_manager.transaction():
    await execute_query("INSERT INTO devices (device_id) VALUES ($1)", "device-001")
    await execute_query("UPDATE device_count SET count = count + 1")
    # 如果任何操作失败，整个事务会回滚
```

### 批量插入

```python
from database.db_manager import db_manager

devices = [
    ("device-001", "Device 1", "1.0.0"),
    ("device-002", "Device 2", "1.0.0"),
    ("device-003", "Device 3", "1.0.0"),
]

await db_manager.execute_many(
    "INSERT INTO devices (device_id, name, version) VALUES ($1, $2, $3)",
    devices
)
```

### JSONB 查询

```sql
-- 查询 current_status JSONB 中的特定字段
SELECT device_id, current_status->'cpu_usage' as cpu_usage
FROM devices
WHERE (current_status->>'cpu_usage')::numeric > 50;

-- 查询 JSONB 数组
SELECT device_id
FROM devices
WHERE 'production' = ANY(tags);
```

## 更多信息

- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
- [asyncpg 文档](https://magicstack.github.io/asyncpg/)
- [PROTOCOL.md](../PROTOCOL.md) - 通信协议规范
