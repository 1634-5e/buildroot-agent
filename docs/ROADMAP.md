# Buildroot Agent 开发路线图

| 项目 | 内容 |
|------|------|
| 版本 | v0.1.0-dev |
| 更新日期 | 2026-03-14 |
| 仓库 | https://github.com/1634-5e/buildroot-agent |

---

## 1. 项目状态

### 1.1 整体进度

| 模块 | 进度 | 状态 |
|------|------|------|
| 架构设计 | 100% | ✅ Python 已下线 |
| Agent C | 100% | ✅ 完成 |
| Rust Server | 100% | ✅ 完成，66 测试通过 |
| Python Server | - | ❌ 已移除 |
| 前端 Web | 80% | Terminal E2E 通过 |
| 测试覆盖 | 60% | E2E 已验证 |
| 监控告警 | 100% | ✅ 完成 |

### 1.2 里程碑

| 里程碑 | 目标 | 状态 | 完成日期 |
|--------|------|------|----------|
| M1 | Device Twin 核心功能 | ✅ | 2026-03-12 |
| M2 | Rust Server 重写 | ✅ | 2026-03-13 |
| M3 | 前端基础功能 | ✅ | 2026-03-14 |
| M3.5 | 告警配置 | ✅ | 2026-03-14 |
| M4 | 架构简化（Python 下线） | ✅ | 2026-03-14 |
| M5 | 测试覆盖完善 | ⏳ | - |
| M6 | 生产就绪 | ⏳ | - |

---

## 2. 已完成工作

### 2.1 后端

| 功能 | 技术栈 | 状态 |
|------|--------|------|
| Device Twin 状态模型 | C / Rust | ✅ |
| MQTT 双向同步 | paho-mqtt / rumqttc | ✅ |
| REST API | Axum | ✅ |
| 设备自动注册 | EMQX REST API | ✅ |
| EMQX ACL 权限控制 | file authorization | ✅ |
| Redis 缓存 | fred | ✅ |
| PostgreSQL 持久化 | SQLx | ✅ |
| Prometheus 指标 | prometheus crate | ✅ |

### 2.2 前端

| 页面 | 功能 | 状态 |
|------|------|------|
| Dashboard | 统计卡片 + 设备预览 + 资源监控 | ✅ |
| 设备列表 | 筛选 + 分页 + 状态标签 | ✅ |
| 设备注册 | 表单 + 凭证展示/复制/下载 | ✅ |
| 设备详情 | 资源监控 + 信息展示 | ✅ |
| Twin 管理 | 编辑 desired + delta 展示 + 变更历史 | ✅ |
| Terminal | xterm.js + WebSocket | ✅ E2E 通过 |
| Files | 文件管理器 | ❌ |
| Alerts | 告警中心 | ❌ |

### 2.3 基础设施

| 服务 | 端口 | 认证 | 状态 |
|------|------|------|------|
| EMQX MQTT | 1883 | 无 | ✅ |
| EMQX Dashboard | 18083 | admin/buildroot123 | ✅ |
| PostgreSQL | 5432 | buildroot/buildroot123 | ✅ |
| Redis | 6379 | buildroot123 | ✅ |
| Rust Server (HTTP) | 8001 | 无 | ✅ |
| Rust Server (Agent TCP) | 8766 | 无 | ✅ |
| Prometheus | 9090 | 无 | ✅ |
| Alertmanager | 9093 | 无 | ✅ |
| Grafana | 3000 | admin/buildroot123 | ✅ |

---

## 3. 问题与改进计划

### 3.1 架构问题

#### 问题 1：服务数量过多（高优先级）

**现状**：Rust Server + Python Server + EMQX 三服务架构

**影响**：运维复杂度高，故障点多

**解决方案**：Rust Server 接管 WebSocket，Python Server 下线

**工作量**：2-3 天

---

#### 问题 2：MQTT Topic 设计复杂（中优先级）

**现状**：
```
twin/{id}/desired      # 状态
status/{id}/heartbeat  # 心跳
metrics/{id}/system    # 指标
alert/{id}/health      # 告警
```

**影响**：ACL 配置繁琐，扩展不便

**解决方案**：合并为 2 个 topic
```
twin/{id}/down  # Server → Agent
twin/{id}/up    # Agent → Server
```

**工作量**：1-2 天

---

#### 问题 3：缓存策略缺失（中优先级）

**现状**：Redis 缓存无 TTL，无失效策略

**影响**：可能读到过期数据

**解决方案**：
- 添加 TTL（1 小时）
- 写穿透失效
- 优雅关闭预热

**工作量**：1 天

---

### 3.2 测试问题

#### 问题 4：缺少集成测试（高优先级）

**现状**：66 个单元测试，全是 mock

**缺失**：
- EMQX ACL 验证
- PostgreSQL 并发
- Redis 断线恢复
- WebSocket 协议

**解决方案**：testcontainers + 真实依赖

**工作量**：2-3 天

---

#### 问题 5：E2E 测试空白（中优先级）

**解决方案**：自动化脚本验证完整流程

**工作量**：1-2 天

---

### 3.3 前端问题

#### 问题 6：Terminal 设备下拉框为空（高优先级）✅ 已修复

**原因**：前端请求 `/api/v1/devices`，Rust Server 只有 `/api/v1/twins`

**解决方案**：Rust Server 添加 `/api/v1/devices` 端点

**工作量**：0.5 天 ✅ 完成

---

#### 问题 7：WebSocket 断线无处理（中优先级）

**解决方案**：自动重连 + 心跳检测

**工作量**：0.5 天

---

### 3.4 运维问题

#### 问题 8：告警未配置（高优先级）

**现状**：Prometheus 规则有，Alertmanager 没有

**解决方案**：Alertmanager + Telegram 通知

**工作量**：0.5 天

---

#### 问题 9：日志分散（中优先级）

**解决方案**：Loki 日志聚合

**工作量**：0.5 天

---

## 4. 开发计划

### Sprint 1：架构简化（1 周）

| # | 任务 | 优先级 | 预计 | 负责 |
|---|------|--------|------|------|
| 1 | Rust Server WebSocket 支持 | P0 | 2d | - |
| 2 | Python Server 下线 | P0 | 1d | - |
| 3 | Terminal bug 修复 | P0 | 0.5d | - |
| 4 | WebSocket 重连机制 | P1 | 0.5d | - |

### Sprint 2：测试完善（1 周）

| # | 任务 | 优先级 | 预计 | 负责 |
|---|------|--------|------|------|
| 5 | 集成测试框架 | P0 | 1d | - |
| 6 | 设备生命周期 E2E | P0 | 1d | - |
| 7 | 并发更新测试 | P1 | 1d | - |
| 8 | MQTT 断线测试 | P1 | 1d | - |

### Sprint 3：运维完善（0.5 周）

| # | 任务 | 优先级 | 预计 | 负责 |
|---|------|--------|------|------|
| 9 | Alertmanager + Telegram | P0 | 0.5d | - |
| 10 | Loki 日志聚合 | P1 | 0.5d | - |
| 11 | 缓存 TTL 策略 | P1 | 0.5d | - |

---

## 5. 技术债务

| # | 项目 | 严重程度 | 状态 |
|---|------|----------|------|
| 1 | Python Server 未删除 | 高 | ✅ 已下线 |
| 2 | MQTT Topic 过多 | 中 | 待处理 |
| 3 | 缓存无 TTL | 中 | 待处理 |
| 4 | Terminal bug | 高 | ✅ 已修复 |
| 5 | 无告警通知 | 高 | ✅ 已修复 |
| 6 | 日志分散 | 中 | 待处理 |

---

## 6. 快速启动

```bash
# 1. 启动基础设施
cd buildroot-agent/buildroot-infra
docker compose up -d

# 2. 启动 Rust Server
cd buildroot-agent/buildroot-server-rs
cargo run

# 3. 启动前端
cd buildroot-agent/buildroot-web-v2
npm run dev

# 4. 运行测试
cd buildroot-agent/buildroot-server-rs
cargo test
```

---

## 7. 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 协议设计 | `docs/PROTOCOL.md` | TCP + MQTT 双通道 |
| Device Twin 设计 | `docs/device-twin-design.md` | 状态模型详细设计 |
| API 文档 | `http://localhost:8001/docs` | OpenAPI Swagger |

---

## 8. 改进行动清单（锐评转化）

### P0 - 必须立即解决

| # | 问题 | 行动 | 状态 |
|---|------|------|------|
| 1 | Python Server 还活着 | Rust Server 接管 WebSocket，Python 下线 | ✅ 已完成 |
| 2 | Terminal 设备下拉框为空 | 修 Pinia 状态管理 bug | ✅ 已修复 |
| 3 | 告警没通知 | Alertmanager + Telegram 配置 | ✅ 已修复 |
| 4 | E2E 测试 | Terminal → Rust → Agent 完整链路 | ✅ 已验证 |

### P1 - 尽快解决

| # | 问题 | 行动 | 状态 |
|---|------|------|------|
| 5 | MQTT Topic 过多 | 合并为 twin/{id}/down + twin/{id}/up | ⏳ |
| 6 | 缓存无 TTL | 添加 1 小时 TTL + 写穿透失效 | ⏳ |
| 7 | WebSocket 断线无处理 | 自动重连 + 心跳检测 | ⏳ |
| 8 | E2E 测试空白 | 自动化脚本验证完整流程 | ⏳ |

### P2 - 可以延后

| # | 问题 | 行动 | 状态 |
|---|------|------|------|
| 9 | 日志分散 | Loki 日志聚合 | ⏳ |
| 10 | Files 组件未开发 | 文件管理器（复杂度高，优先 Alerts） | ⏳ |

---

*最后更新：2026-03-14*