# Device Twin 开发任务拆解

> 创建时间: 2026-03-11
> 预计总工期: 12 周
> 状态: 待开始

---

## 任务总览

```
Phase 1: 基础设施搭建 ──────────────────────────────── 2 周
Phase 2: Agent 端开发 ──────────────────────────────── 3 周
Phase 3: Server 端开发 ─────────────────────────────── 2 周
Phase 4: 功能迁移 ──────────────────────────────────── 3 周
Phase 5: OTA 集成 ───────────────────────────────────── 2 周
Phase 6: 测试与上线 ─────────────────────────────────── 持续
```

---

## Phase 1: 基础设施搭建（2 周）

### 1.1 MQTT Broker 部署

**优先级: P0** | **工期: 3 天** | **依赖: 无**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 1.1.1 | 选型评估：EMQX vs Mosquitto | 0.5d | - | 待开始 |
| 1.1.2 | Docker Compose 配置文件编写 | 0.5d | - | 待开始 |
| 1.1.3 | ACL 权限配置 | 0.5d | - | 待开始 |
| 1.1.4 | TLS 证书配置 | 0.5d | - | 待开始 |
| 1.1.5 | 监控指标暴露（Prometheus） | 0.5d | - | 待开始 |
| 1.1.6 | 高可用集群部署文档 | 0.5d | - | 待开始 |

#### 验收标准

- [ ] MQTT Broker 可通过 `mqtt://localhost:1883` 访问
- [ ] 支持 TLS 加密连接
- [ ] ACL 配置生效，设备只能访问自己的 topic
- [ ] Prometheus 可抓取 Broker 指标
- [ ] 有完整部署文档

#### 技术要点

```yaml
# docker-compose.yml 示例
version: '3.8'
services:
  emqx:
    image: emqx/emqx:5.0
    container_name: emqx
    environment:
      - EMQX_NAME=emqx
      - EMQX_HOST=0.0.0.0
    ports:
      - "1883:1883"      # MQTT
      - "8883:8883"      # MQTT/TLS
      - "8083:8083"      # WebSocket
      - "18083:18083"    # Dashboard
    volumes:
      - ./emqx/etc:/opt/emqx/etc
      - ./emqx/data:/opt/emqx/data
      - ./emqx/log:/opt/emqx/log
```

---

### 1.2 数据库表结构创建

**优先级: P0** | **工期: 2 天** | **依赖: 无**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 1.2.1 | 编写 PostgreSQL migration 文件 | 0.5d | - | 待开始 |
| 1.2.2 | 创建 device_twins 表 | 0.25d | - | 待开始 |
| 1.2.3 | 创建 twin_change_logs 表 | 0.25d | - | 待开始 |
| 1.2.4 | 创建索引和触发器 | 0.25d | - | 待开始 |
| 1.2.5 | 编写测试数据脚本 | 0.25d | - | 待开始 |
| 1.2.6 | 文档：数据库 schema 说明 | 0.5d | - | 待开始 |

#### 验收标准

- [ ] migration 可重复执行，幂等
- [ ] 所有索引创建成功
- [ ] 触发器自动更新 `updated_at`
- [ ] 测试数据可插入

#### SQL 文件

```sql
-- migrations/001_create_twin_tables.sql

-- 设备孪生主表
CREATE TABLE IF NOT EXISTS device_twins (
    device_id VARCHAR(64) PRIMARY KEY,
    desired JSONB NOT NULL DEFAULT '{}',
    desired_version BIGINT NOT NULL DEFAULT 0,
    desired_at TIMESTAMP WITH TIME ZONE,
    desired_by VARCHAR(128),
    reported JSONB NOT NULL DEFAULT '{}',
    reported_version BIGINT NOT NULL DEFAULT 0,
    reported_at TIMESTAMP WITH TIME ZONE,
    tags JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT valid_device_id CHECK (device_id ~ '^[A-Za-z0-9_-]+$')
);

-- 变更历史表
CREATE TABLE IF NOT EXISTS twin_change_logs (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES device_twins(device_id) ON DELETE CASCADE,
    change_type VARCHAR(16) NOT NULL,
    old_value JSONB,
    new_value JSONB,
    changed_by VARCHAR(128),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT valid_change_type CHECK (change_type IN ('desired', 'reported'))
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_twins_desired_at ON device_twins(desired_at DESC);
CREATE INDEX IF NOT EXISTS idx_twins_reported_at ON device_twins(reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_twins_tags ON device_twins USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_change_logs_device ON twin_change_logs(device_id, changed_at DESC);

-- 触发器函数
CREATE OR REPLACE FUNCTION update_twin_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 触发器
DROP TRIGGER IF EXISTS twin_updated ON device_twins;
CREATE TRIGGER twin_updated
    BEFORE UPDATE ON device_twins
    FOR EACH ROW
    EXECUTE FUNCTION update_twin_timestamp();
```

---

### 1.3 Redis 配置

**优先级: P0** | **工期: 1 天** | **依赖: 无**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 1.3.1 | Redis Docker 配置 | 0.25d | - | 待开始 |
| 1.3.2 | Key 命名规范文档 | 0.25d | - | 待开始 |
| 1.3.3 | 连接池配置 | 0.25d | - | 待开始 |
| 1.3.4 | TTL 策略配置 | 0.25d | - | 待开始 |

#### Key 设计

```
twin:{device_id}:desired       -> JSON (期望状态)
twin:{device_id}:reported      -> JSON (已报告状态)
twin:{device_id}:delta         -> JSON (差异)
twin:{device_id}:version       -> Hash {desired_v, reported_v}
twin:{device_id}:connected     -> 1/0 (在线状态, TTL 300s)
twin:{device_id}:last_seen     -> Timestamp
```

---

### 1.4 开发环境脚本

**优先级: P1** | **工期: 1 天** | **依赖: 1.1, 1.2, 1.3**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 1.4.1 | 一键启动脚本 `scripts/dev-up.sh` | 0.25d | - | 待开始 |
| 1.4.2 | 一键停止脚本 `scripts/dev-down.sh` | 0.25d | - | 待开始 |
| 1.4.3 | 数据重置脚本 `scripts/dev-reset.sh` | 0.25d | - | 待开始 |
| 1.4.4 | 环境变量配置 `.env.example` | 0.25d | - | 待开始 |

---

## Phase 2: Agent 端开发（3 周）

### 2.1 Twin 状态管理模块

**优先级: P0** | **工期: 4 天** | **依赖: Phase 1**

#### 文件结构

```
buildroot-agent/src/twin/
├── twin_state.h          # 状态结构定义
├── twin_state.c          # 状态管理实现
├── twin_diff.h           # 差异计算接口
├── twin_diff.c           # 差异计算实现
├── twin_persist.h        # 持久化接口
├── twin_persist.c        # 持久化实现
└── CMakeLists.txt        # 编译配置
```

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 2.1.1 | 定义 `twin_state_t` 结构体 | 0.5d | - | 待开始 |
| 2.1.2 | 实现 `twin_init/destroy` | 0.25d | - | 待开始 |
| 2.1.3 | 实现 `twin_set_desired` | 0.5d | - | 待开始 |
| 2.1.4 | 实现 `twin_update_reported` | 0.5d | - | 待开始 |
| 2.1.5 | 实现 `compute_delta` 差异计算 | 1d | - | 待开始 |
| 2.1.6 | 实现版本检查逻辑 | 0.25d | - | 待开始 |
| 2.1.7 | 单元测试 | 0.5d | - | 待开始 |
| 2.1.8 | 集成到 CMake | 0.25d | - | 待开始 |

#### 验收标准

- [ ] 所有 API 有完整注释
- [ ] 单元测试覆盖率 > 80%
- [ ] 内存泄漏检查通过 (valgrind)
- [ ] 可独立编译为静态库

---

### 2.2 Twin 持久化模块

**优先级: P0** | **工期: 2 天** | **依赖: 2.1**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 2.2.1 | 实现 `twin_load` 从文件加载 | 0.5d | - | 待开始 |
| 2.2.2 | 实现 `twin_save` 保存到文件 | 0.5d | - | 待开始 |
| 2.2.3 | 文件锁防止并发写入 | 0.25d | - | 待开始 |
| 2.2.4 | 原子写入（先写临时文件再 rename） | 0.25d | - | 待开始 |
| 2.2.5 | 单元测试 | 0.25d | - | 待开始 |
| 2.2.6 | 错误恢复（文件损坏时） | 0.25d | - | 待开始 |

#### 文件格式

```json
// /var/lib/agent/twin.json
{
  "deviceId": "HTCU-开发板-001",
  "desired": {
    "version": 5,
    "data": { ... },
    "receivedAt": "2026-03-11T12:00:00Z"
  },
  "reported": {
    "version": 5,
    "data": { ... }
  },
  "pending": {
    // 待执行的 delta
  }
}
```

---

### 2.3 MQTT 客户端集成

**优先级: P0** | **工期: 3 天** | **依赖: 2.1**

#### 文件结构

```
buildroot-agent/src/transport/
├── mqtt_client.h         # MQTT 客户端接口
├── mqtt_client.c         # MQTT 客户端实现
├── mqtt_config.h         # MQTT 配置
└── CMakeLists.txt
```

#### 子任务

| ID | 任务 | 鐁计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 2.3.1 | 选择 MQTT 库（paho.mqtt.c / mosquitto） | 0.25d | - | 待开始 |
| 2.3.2 | 封装连接/断开/订阅/发布 API | 0.5d | - | 待开始 |
| 2.3.3 | 实现断线重连机制 | 0.5d | - | 待开始 |
| 2.3.4 | 实现 QoS 1 消息确认 | 0.5d | - | 待开始 |
| 2.3.5 | 集成 TLS 证书认证 | 0.5d | - | 待开始 |
| 2.3.6 | 消息回调机制 | 0.25d | - | 待开始 |
| 2.3.7 | 单元测试 | 0.5d | - | 待开始 |

#### MQTT 库选择

| 库 | 优点 | 缺点 |
|----|------|------|
| **paho.mqtt.c** | Eclipse 官方，文档完善，功能全面 | 依赖较多 |
| **mosquitto** | 轻量，广泛使用 | API 较底层 |

**推荐**: `paho.mqtt.c`，功能更完善，社区活跃。

---

### 2.4 Twin 同步模块

**优先级: P0** | **工期: 3 天** | **依赖: 2.1, 2.3**

#### 文件结构

```
buildroot-agent/src/twin/
├── twin_sync.h           # 同步接口
├── twin_sync.c           # 同步实现
├── twin_mqtt.c           # MQTT 传输层
└── twin_tcp.c            # TCP 传输层（备用）
```

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 2.4.1 | 设计 MQTT Topic 命名 | 0.25d | - | 待开始 |
| 2.4.2 | 实现 `twin_sync_init` | 0.5d | - | 待开始 |
| 2.4.3 | 实现 `twin_sync_report` 上报状态 | 0.5d | - | 待开始 |
| 2.4.4 | 实现 `twin_sync_full` 全量同步 | 0.5d | - | 待开始 |
| 2.4.5 | 实现 MQTT 消息解析和回调 | 0.5d | - | 待开始 |
| 2.4.6 | 实现启动时同步流程 | 0.25d | - | 待开始 |
| 2.4.7 | 单元测试 | 0.5d | - | 待开始 |

#### Topic 设计

```
twin/{device_id}/desired     # 订阅：接收期望状态
twin/{device_id}/reported    # 发布：上报已报告状态
twin/{device_id}/cmd         # 发布：请求命令（如 getDesired）
```

---

### 2.5 业务处理器集成

**优先级: P1** | **工期: 3 天** | **依赖: 2.4**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 2.5.1 | 实现 `agent_ota_handle_twin` | 1d | - | 待开始 |
| 2.5.2 | 实现 `agent_config_apply_twin` | 1d | - | 待开始 |
| 2.5.3 | 实现 `on_delta_changed` 回调 | 0.5d | - | 待开始 |
| 2.5.4 | 集成测试 | 0.5d | - | 待开始 |

---

### 2.6 主循环集成

**优先级: P0** | **工期: 1 天** | **依赖: 2.1-2.5**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 2.6.1 | 修改 `agent_main.c` 集成 Twin | 0.5d | - | 待开始 |
| 2.6.2 | 实现定期上报系统状态 | 0.25d | - | 待开始 |
| 2.6.3 | 实现定期保存本地状态 | 0.25d | - | 待开始 |

---

## Phase 3: Server 端开发（2 周）

### 3.1 Twin Service 核心实现

**优先级: P0** | **工期: 3 天** | **依赖: Phase 1**

#### 文件结构

```
buildroot-server/twin/
├── __init__.py
├── models.py             # 数据模型
├── service.py            # 核心服务
├── repository.py         # 数据访问层
└── exceptions.py         # 异常定义
```

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 3.1.1 | 定义 `DeviceTwin` Pydantic 模型 | 0.5d | - | 待开始 |
| 3.1.2 | 实现 `TwinRepository` 数据访问层 | 1d | - | 待开始 |
| 3.1.3 | 实现 `TwinService` 业务逻辑 | 1d | - | 待开始 |
| 3.1.4 | 实现 delta 计算算法 | 0.5d | - | 待开始 |

---

### 3.2 REST API 实现

**优先级: P0** | **工期: 2 天** | **依赖: 3.1**

#### 文件结构

```
buildroot-server/api/v1/
├── twin.py               # Twin API 路由
└── schemas.py            # 请求/响应 schema
```

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 3.2.1 | 实现 `GET /devices/{id}/twin` | 0.5d | - | 待开始 |
| 3.2.2 | 实现 `PATCH /devices/{id}/twin` | 0.5d | - | 待开始 |
| 3.2.3 | 实现 `POST /twins/batch` 批量操作 | 0.5d | - | 待开始 |
| 3.2.4 | 实现 `GET /devices/{id}/twin/history` | 0.5d | - | 待开始 |
| 3.2.5 | API 文档（OpenAPI） | 0.25d | - | 待开始 |
| 3.2.6 | 单元测试 | 0.5d | - | 待开始 |

---

### 3.3 MQTT 消息处理

**优先级: P0** | **工期: 2 天** | **依赖: 3.1**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 3.3.1 | 实现 MQTT 客户端连接 | 0.5d | - | 待开始 |
| 3.3.2 | 实现订阅 `twin/+/reported` | 0.25d | - | 待开始 |
| 3.3.3 | 实现消息解析和处理 | 0.5d | - | 待开始 |
| 3.3.4 | 实现推送 desired 到设备 | 0.5d | - | 待开始 |
| 3.3.5 | 单元测试 | 0.25d | - | 待开始 |

---

### 3.4 WebSocket 推送

**优先级: P1** | **工期: 2 天** | **依赖: 3.1**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 3.4.1 | 实现 WebSocket 连接管理 | 0.5d | - | 待开始 |
| 3.4.2 | 实现 twin 变更推送 | 0.5d | - | 待开始 |
| 3.4.3 | 实现房间管理（按设备 ID） | 0.5d | - | 待开始 |
| 3.4.4 | 单元测试 | 0.5d | - | 待开始 |

---

## Phase 4: 功能迁移（3 周）

### 4.1 状态上报迁移

**优先级: P0** | **工期: 3 天** | **依赖: Phase 2, 3**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 4.1.1 | Agent: 系统状态上报改为 Twin | 1d | - | 待开始 |
| 4.1.2 | Server: 兼容处理老版本状态 | 0.5d | - | 待开始 |
| 4.1.3 | Web: 状态展示适配新 API | 1d | - | 待开始 |
| 4.1.4 | 集成测试 | 0.5d | - | 待开始 |

---

### 4.2 配置下发迁移

**优先级: P0** | **工期: 4 天** | **依赖: Phase 2, 3**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 4.2.1 | Agent: 配置应用对接 Twin | 1d | - | 待开始 |
| 4.2.2 | Server: 配置管理 API | 1d | - | 待开始 |
| 4.2.3 | Web: 配置编辑界面 | 1d | - | 待开始 |
| 4.2.4 | 灰度测试 | 1d | - | 待开始 |

---

### 4.3 灰度发布系统

**优先级: P1** | **工期: 3 天** | **依赖: 4.1, 4.2**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 4.3.1 | 灰度标签配置 API | 1d | - | 待开始 |
| 4.3.2 | 灰度策略执行 | 1d | - | 待开始 |
| 4.3.3 | 灰度监控面板 | 1d | - | 待开始 |

---

### 4.4 协议文档更新

**优先级: P1** | **工期: 1 天** | **依赖: 4.1-4.3**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 4.4.1 | 更新 PROTOCOL.md | 0.5d | - | 待开始 |
| 4.4.2 | 更新 AGENTS.md | 0.25d | - | 待开始 |
| 4.4.3 | 编写迁移指南 | 0.25d | - | 待开始 |

---

## Phase 5: OTA 集成（2 周）

### 5.1 Twin 驱动的 OTA 流程

**优先级: P0** | **工期: 4 天** | **依赖: Phase 4**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 5.1.1 | 设计 Twin 中的 firmware 结构 | 0.5d | - | 待开始 |
| 5.1.2 | Agent: OTA 模块对接 Twin | 1.5d | - | 待开始 |
| 5.1.3 | Server: OTA 审批流程适配 | 1d | - | 待开始 |
| 5.1.4 | 集成测试 | 1d | - | 待开始 |

---

### 5.2 回滚与错误处理

**优先级: P0** | **工期: 2 天** | **依赖: 5.1**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 5.2.1 | Agent: OTA 失败自动回滚 | 0.5d | - | 待开始 |
| 5.2.2 | Agent: 失败状态上报 | 0.5d | - | 待开始 |
| 5.2.3 | Server: 失败告警 | 0.5d | - | 待开始 |
| 5.2.4 | 测试 | 0.5d | - | 待开始 |

---

### 5.3 批量 OTA

**优先级: P1** | **工期: 2 天** | **依赖: 5.1**

#### 子任务

| ID | 任务 | 预计 | 负责人 | 状态 |
|----|------|------|--------|------|
| 5.3.1 | 批量设置 firmware desired | 0.5d | - | 待开始 |
| 5.3.2 | 进度跟踪 | 0.5d | - | 待开始 |
| 5.3.3 | 分批发布策略 | 0.5d | - | 待开始 |
| 5.3.4 | Web 界面 | 0.5d | - | 待开始 |

---

## Phase 6: 测试与上线（持续）

### 6.1 测试

| 测试类型 | 范围 | 负责人 | 状态 |
|----------|------|--------|------|
| 单元测试 | Agent C 代码覆盖率 > 80% | - | 待开始 |
| 单元测试 | Server Python 代码覆盖率 > 80% | - | 待开始 |
| 集成测试 | Agent + Server + MQTT 端到端 | - | 待开始 |
| 契约测试 | 消息格式兼容性 | - | 待开始 |
| 压力测试 | 1000 设备并发 | - | 待开始 |
| 故障测试 | MQTT 断开、网络延迟 | - | 待开始 |

### 6.2 文档

| 文档 | 状态 |
|------|------|
| Device Twin 设计文档 | ✅ 已完成 |
| API 文档 | 待开始 |
| Agent 开发指南 | 待开始 |
| 部署指南 | 待开始 |
| 运维手册 | 待开始 |

### 6.3 监控告警

| 指标 | 告警阈值 | 状态 |
|------|----------|------|
| MQTT 连接数 | < 预期的 50% | 待配置 |
| Twin 同步延迟 | > 30s | 待配置 |
| 数据库写入延迟 | > 100ms | 待配置 |
| Redis 缓存命中率 | < 80% | 待配置 |

---

## 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| MQTT Broker 单点故障 | 高 | 中 | 部署 EMQX 集群 |
| 数据库性能瓶颈 | 中 | 低 | 引入 Redis 缓存，优化索引 |
| Agent 固件兼容性 | 高 | 中 | 灰度发布，保留 TCP 回退通道 |
| 消息丢失 | 高 | 低 | MQTT QoS 1，本地持久化 |
| 并发冲突 | 中 | 中 | 乐观锁 + 版本号 |

---

## 里程碑

| 里程碑 | 目标日期 | 状态 |
|--------|----------|------|
| M1: 基础设施就绪 | Week 2 | 待开始 |
| M2: Agent Twin 模块可用 | Week 5 | 待开始 |
| M3: Server Twin API 可用 | Week 7 | 待开始 |
| M4: 状态上报迁移完成 | Week 9 | 待开始 |
| M5: OTA 集成完成 | Week 11 | 待开始 |
| M6: 全量上线 | Week 12 | 待开始 |

---

## 下一步行动

1. **立即**：确认 MQTT Broker 选型（EMQX vs Mosquitto）
2. **本周**：完成 Phase 1 基础设施搭建
3. **下周**：启动 Phase 2 Agent 端开发

---

*最后更新: 2026-03-11*