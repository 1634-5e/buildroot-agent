# Dashboard 重构需求

## 目标
将 Dashboard 从单纯的"设备列表+聚合资源"升级为"系统控制中心"视角。

## 设计方案

### 布局
```
┌─────────────────────────────────────────────────────────┐
│  SYSTEM STATUS (顶部状态卡片区)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Server   │ │ Agents   │ │ Sessions │ │ Health   │   │
│  │ ● online │ │ 12/15    │ │ 8 active │ │ ▲ 98%    │   │
│  │ cpu 23%  │ │ 3 offline│ │ 2 pending│ │ 1 alert  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
├─────────────────────────────────────────────────────────┤
│  左侧: AGGREGATE RESOURCES  │  右侧: ALERTS / EVENTS    │
│  ┌─────────────────────────┐│  ┌───────────────────────┐│
│  │ CPU ████░░░░ 42%        ││  │ ⚠ device-abc CPU 95%  ││
│  │ MEM ███░░░░░ 38%        ││  │ ⚠ device-xyz offline  ││
│  │ NET ↑2.3MB ↓8.1MB       ││  │ ✓ update completed    ││
│  │ DISK ██░░░░░░ 21%       ││  └───────────────────────┘│
│  └─────────────────────────┘│                           │
├─────────────────────────────────────────────────────────┤
│  DEVICES (紧凑卡片网格)                                 │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐      │
│  │●abc │ │●xyz │ │●123 │ │○456 │ │●789 │ │○def │      │
│  │42%  │ │95%⚠│ │18%  │ │off  │ │67%  │ │off  │      │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘      │
└─────────────────────────────────────────────────────────┘
```

### 功能模块

#### 1. 顶部状态卡片
- **Server Card**: 服务器状态、CPU、内存、运行时间
- **Agents Card**: 在线/总数、离线数量
- **Sessions Card**: 活跃终端会话、文件传输中
- **Health Card**: 系统健康评分 (0-100)，告警数量

#### 2. 左侧聚合资源
- 保持现有设计，但更紧凑
- 添加趋势指示 (↑↓)

#### 3. 右侧告警/事件
- 实时告警: CPU > 80%、内存 > 90%、设备离线
- 最近事件: 命令完成、文件传输、连接/断开
- 支持点击跳转到对应设备

#### 4. 设备网格
- 紧凑小卡片: 只显示 状态灯 + 名称(6字符) + CPU%
- 一屏可显示 20+ 设备
- 点击展开详情面板(右侧滑出或模态框)
- 异常设备高亮(红色边框/背景)

### 技术要点

1. **新增 API**:
   - GET /api/system/health - 健康评分
   - GET /api/system/alerts - 告警列表
   - GET /api/system/events - 最近事件

2. **新增 Store**:
   - src/stores/system.ts - 系统状态管理

3. **新增组件**:
   - src/components/SystemStatusCard.vue
   - src/components/AlertPanel.vue
   - src/components/DeviceMiniCard.vue

4. **修改文件**:
   - src/views/Dashboard/index.vue - 重写布局
   - buildroot-server/server/http_server.py - 新增 API

### 设计风格
- 深色主题，工业风
- 参考 Grafana / Datadog 的 Dashboard 设计
- 强调"一眼看出系统状态"

## 文件位置
- 前端: buildroot-web-vue/
- 后端: buildroot-server/

请先实现前端 UI 重构，API 可以先用 mock 数据。
