# Rust Server 重写计划

## 概述

将 Python FastAPI Server 重写为 Rust (Axum + SQLx)，保持 API 兼容，提升性能和类型安全。

## 技术栈

| 功能 | Crate | 说明 |
|------|-------|------|
| Web 框架 | `axum` | Tower 生态，类型安全 |
| 异步运行时 | `tokio` | 1.x，主流选择 |
| PostgreSQL | `sqlx` | 编译时 SQL 检查 |
| Redis | `fred` | 异步，性能好 |
| MQTT | `rumqttc` | 纯 Rust，易用 |
| 序列化 | `serde` + `serde_json` | 标准 |
| 配置 | `config` + `dotenvy` | 环境变量 + 文件 |
| 日志 | `tracing` + `tracing-subscriber` | 结构化日志 |
| Metrics | `prometheus` + `axum-prometheus` | Prometheus 集成 |
| 错误处理 | `thiserror` + `anyhow` | 错误类型定义 |

---

## Phase 1: 项目骨架 + 基础设施连接

**目标**: 跑起来一个健康检查端点，能连 PostgreSQL 和 Redis

### 1.1 项目初始化

```bash
cargo init buildroot-server-rs
cd buildroot-server-rs
```

### 1.2 依赖 (Cargo.toml)

```toml
[dependencies]
# Web
axum = { version = "0.7", features = ["macros"] }
tokio = { version = "1", features = ["full"] }
tower = "0.4"
tower-http = { version = "0.5", features = ["cors", "trace"] }

# Database
sqlx = { version = "0.7", features = ["runtime-tokio", "postgres", "json", "chrono"] }
fred = { version = "8", features = ["enable-rustls"] }

# MQTT
rumqttc = "0.24"

# Serialization
serde = { version = "1", features = ["derive"] }
serde_json = "1"

# Config
config = "0.14"
dotenvy = "0.15"

# Logging
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }

# Error
thiserror = "1"
anyhow = "1"

# Metrics
prometheus = "0.13"
axum-prometheus = "0.6"

# Utils
chrono = { version = "0.4", features = ["serde"] }
uuid = { version = "1", features = ["v4", "serde"] }
rand = "0.8"
reqwest = { version = "0.12", features = ["json"] }
```

### 1.3 目录结构

```
buildroot-server-rs/
├── Cargo.toml
├── .env
├── src/
│   ├── main.rs              # 入口 + 生命周期
│   ├── config.rs            # 配置结构
│   ├── error.rs             # 错误类型
│   ├── state.rs             # 应用状态
│   ├── db/
│   │   ├── mod.rs
│   │   └── postgres.rs      # 连接池初始化
│   └── redis/
│       ├── mod.rs
│       └── client.rs        # Redis 连接
```

### 1.4 交付物

- [ ] `Cargo.toml` 依赖配置
- [ ] `config.rs` 配置加载
- [ ] PostgreSQL 连接池
- [ ] Redis 连接
- [ ] `/health` 端点返回 DB 状态
- [ ] `/` 根路径返回服务信息

---

## Phase 2: 数据模型 + Twin Service

**目标**: 实现 Twin 核心逻辑，PostgreSQL 读写

### 2.1 目录结构扩展

```
src/
├── models/
│   ├── mod.rs
│   └── twin.rs              # DeviceTwin, TwinUpdate 等
├── twin/
│   ├── mod.rs
│   └── service.rs           # TwinService 核心逻辑
```

### 2.2 数据模型 (models/twin.rs)

```rust
pub struct DeviceTwin {
    pub device_id: String,
    pub desired: serde_json::Value,
    pub desired_version: i64,
    pub reported: serde_json::Value,
    pub reported_version: i64,
    pub tags: serde_json::Value,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub updated_at: chrono::DateTime<chrono::Utc>,
}

pub struct TwinUpdate {
    pub desired: serde_json::Value,
}

pub struct TwinOverview {
    pub device_id: String,
    pub desired: serde_json::Value,
    pub reported: serde_json::Value,
    pub delta: serde_json::Value,
    pub is_synced: bool,
    // ...
}
```

### 2.3 TwinService 核心方法

```rust
impl TwinService {
    pub async fn get_twin(&self, device_id: &str) -> Result<Option<DeviceTwin>>;
    pub async fn update_desired(&self, device_id: &str, desired: Value, updated_by: &str) -> Result<DeviceTwin>;
    pub async fn update_reported(&self, device_id: &str, reported: Value, version: i64) -> Result<DeviceTwin>;
    pub async fn get_history(&self, device_id: &str, limit: i64) -> Result<Vec<ChangeLog>>;
    pub async fn batch_update(&self, device_ids: &[String], desired: Value) -> Result<usize>;
    pub async fn register_device(&self, req: RegisterRequest) -> Result<RegisterResponse>;
}
```

### 2.4 交付物

- [ ] 数据模型定义
- [ ] TwinService 实现
- [ ] PostgreSQL CRUD 操作
- [ ] Redis 缓存读写
- [ ] Delta 计算逻辑
- [ ] 单元测试

---

## Phase 3: REST API 端点

**目标**: 实现所有 API 端点，Axum 路由

### 3.1 目录结构扩展

```
src/
├── api/
│   ├── mod.rs
│   └── v1/
│       ├── mod.rs
│       └── twin.rs           # Twin 相关路由
```

### 3.2 API 端点

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/` | 服务信息 |
| GET | `/health` | 健康检查 |
| GET | `/metrics` | Prometheus 指标 |
| GET | `/api/v1/devices/{device_id}/twin` | 获取 Twin |
| PATCH | `/api/v1/devices/{device_id}/twin` | 更新 desired |
| GET | `/api/v1/devices/{device_id}/twin/history` | 变更历史 |
| POST | `/api/v1/twins/batch` | 批量更新 |
| GET | `/api/v1/twins` | 列出所有 Twin |
| POST | `/api/v1/register` | 设备注册 |

### 3.3 交付物

- [ ] Axum 路由配置
- [ ] 所有端点实现
- [ ] 请求验证
- [ ] 错误响应格式化
- [ ] CORS 中间件

---

## Phase 4: MQTT 集成

**目标**: MQTT 客户端，订阅 reported，推送 desired

### 4.1 目录结构扩展

```
src/
├── mqtt/
│   ├── mod.rs
│   └── handler.rs            # MQTT 消息处理
```

### 4.2 MQTT 功能

```rust
impl MqttHandler {
    pub async fn connect(&mut self) -> Result<()>;
    pub async fn subscribe_reported(&mut self, device_id: &str) -> Result<()>;
    pub async fn publish_desired(&self, device_id: &str, desired: &Value, version: i64) -> Result<()>;
    pub async fn handle_message(&self, topic: &str, payload: &[u8]) -> Result<()>;
}
```

### 4.3 Topic 设计 (保持与 Python 一致)

| Topic | 方向 | 用途 |
|-------|------|------|
| `twin/{device_id}/desired` | Server → Agent | 期望状态 |
| `twin/{device_id}/reported` | Agent → Server | 已报告状态 |

### 4.4 交付物

- [ ] MQTT 连接管理
- [ ] 订阅 reported topic
- [ ] 发布 desired topic
- [ ] 消息解析与处理
- [ ] 重连机制

---

## Phase 5: EMQX 集成

**目标**: EMQX REST API 客户端，设备注册 + ACL

### 5.1 目录结构扩展

```
src/
├── emqx/
│   ├── mod.rs
│   └── client.rs             # EMQX REST API
```

### 5.2 EMQX Client 功能

```rust
impl EmqxClient {
    pub async fn create_device_user(&self, device_id: &str, password: &str) -> Result<()>;
    pub async fn delete_device_user(&self, device_id: &str) -> Result<()>;
    pub async fn setup_device_acl(&self, device_id: &str) -> Result<()>;
}
```

### 5.3 交付物

- [ ] EMQX REST API 封装
- [ ] 设备用户创建
- [ ] ACL 规则配置
- [ ] 错误处理

---

## Phase 6: Metrics + 测试 + 文档

**目标**: Prometheus 集成，测试覆盖，部署文档

### 6.1 Metrics 端点

```rust
// 指标
lazy_static! {
    pub static ref HTTP_REQUESTS: CounterVec = ...;
    pub static ref DEVICES_TOTAL: Gauge = ...;
    pub static ref DEVICES_ONLINE: Gauge = ...;
    pub static ref TWIN_UPDATES: CounterVec = ...;
    pub static ref MQTT_MESSAGES: CounterVec = ...;
}
```

### 6.2 测试

- 单元测试: TwinService 核心逻辑
- 集成测试: API 端点 (使用 test containers)
- 负载测试: 并发请求

### 6.3 交付物

- [ ] `/metrics` 端点
- [ ] 单元测试
- [ ] 集成测试
- [ ] Docker 构建配置
- [ ] 部署文档

---

## 时间估算

| Phase | 预估时间 |
|-------|----------|
| Phase 1 | 2-3 小时 |
| Phase 2 | 4-5 小时 |
| Phase 3 | 3-4 小时 |
| Phase 4 | 3-4 小时 |
| Phase 5 | 2-3 小时 |
| Phase 6 | 3-4 小时 |
| **总计** | **17-23 小时** |

---

## 迁移策略

1. **并行运行**: 新 Rust server 与 Python server 同时运行，端口错开
2. **功能验证**: 逐个端点切换，验证行为一致
3. **性能对比**: 压测对比，确认提升
4. **完全切换**: 确认无问题后切换到 Rust

---

## 下一步

开始 Phase 1？我会创建项目骨架，配置依赖，实现健康检查端点。