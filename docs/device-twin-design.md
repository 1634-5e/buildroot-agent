# Device Twin 设计规范

> 版本: 1.0.0-draft
> 状态: 设计评审中
> 作者: Architecture Review
> 日期: 2026-03-11

---

## 目录

- [1. 概述](#1-概述)
- [2. 核心概念](#2-核心概念)
- [3. 数据模型](#3-数据模型)
- [4. Agent 端实现](#4-agent-端实现)
- [5. Server 端实现](#5-server-端实现)
- [6. 同步协议](#6-同步协议)
- [7. 边界情况处理](#7-边界情况处理)
- [8. 与现有系统兼容](#8-与现有系统兼容)
- [9. 迁移路径](#9-迁移路径)
- [10. 测试策略](#10-测试策略)

---

## 1. 概述

### 1.1 问题背景

当前系统采用"命令式"架构：
- Server 下发命令 → Agent 执行 → 返回结果
- Agent 离线时无法接收命令
- 状态仅在内存中，Server 重启后丢失
- 无法查询设备"应该是什么状态"

### 1.2 目标

引入 Device Twin（设备孪生）模式：
- **声明式状态管理**：Server 定义期望状态，Agent 自动收敛
- **离线可用**：设备离线时仍可修改期望状态，上线后自动同步
- **状态持久化**：所有状态存储在数据库，可查询历史
- **渐进式迁移**：与现有 TCP 协议并存，零风险

### 1.3 适用场景

| 场景 | Device Twin 适用性 |
|------|-------------------|
| 配置下发 | ✅ 完美适用 |
| 固件更新 | ✅ 完美适用 |
| 状态查询 | ✅ 完美适用 |
| 实时命令 | ⚠️ 不适用，仍用 TCP |
| PTY 终端 | ❌ 不适用，仍用 TCP |
| 文件传输 | ❌ 不适用，仍用 TCP |

---

## 2. 核心概念

### 2.1 Twin 三要素

```
┌─────────────────────────────────────────────────────────┐
│                    Device Twin                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  desired (期望状态)                                      │
│  ├── 由云端定义                                          │
│  ├── 表示"设备应该变成什么样子"                           │
│  └── 设备离线时仍可修改                                   │
│                                                         │
│  reported (已报告状态)                                   │
│  ├── 由设备上报                                          │
│  ├── 表示"设备当前实际状态"                               │
│  └── 仅设备可修改                                        │
│                                                         │
│  delta (差异)                                           │
│  ├── 自动计算：desired ∩ reported 的差集                 │
│  ├── 表示"设备需要执行的操作"                             │
│  └── 设备执行后上报 reported，delta 自动缩小              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2.2 状态示例

```json
{
  "deviceId": "HTCU-开发板-001",
  "desired": {
    "firmware": {
      "version": "2.1.0",
      "url": "https://updates.example.com/firmware-2.1.0.bin",
      "checksum": "sha256:abc123..."
    },
    "config": {
      "sampleRate": 1000,
      "logLevel": "info",
      "network": {
        "heartbeatInterval": 30,
        "retryCount": 3
      }
    },
    "metadata": {
      "desiredAt": "2026-03-11T12:00:00Z",
      "desiredBy": "admin@example.com"
    }
  },
  "reported": {
    "firmware": {
      "version": "2.0.5",
      "installedAt": "2026-03-01T08:00:00Z"
    },
    "config": {
      "sampleRate": 1000,
      "logLevel": "debug",
      "network": {
        "heartbeatInterval": 30,
        "retryCount": 3
      }
    },
    "system": {
      "cpuUsage": 23.5,
      "memFree": 456789,
      "uptime": 864000,
      "lastBoot": "2026-03-01T08:00:00Z"
    },
    "metadata": {
      "reportedAt": "2026-03-11T12:30:00Z"
    }
  },
  "delta": {
    "firmware": {
      "version": "2.1.0",
      "url": "https://updates.example.com/firmware-2.1.0.bin",
      "checksum": "sha256:abc123..."
    },
    "config": {
      "logLevel": "info"
    }
  }
}
```

### 2.3 状态分类

| 类别 | 存储位置 | 修改方 | 示例 |
|------|----------|--------|------|
| **配置状态** | desired + reported | 双向同步 | 采样率、日志级别 |
| **固件状态** | desired + reported | 云端发起 | 版本、更新 URL |
| **系统状态** | reported only | 设备上报 | CPU、内存、温度 |
| **元数据** | tags | 云端管理 | 位置、所属项目 |

---

## 3. 数据模型

### 3.1 Server 端数据库设计

#### PostgreSQL（持久化存储）

```sql
-- 设备孪生主表
CREATE TABLE device_twins (
    device_id VARCHAR(64) PRIMARY KEY,
    
    -- 期望状态（云端定义）
    desired JSONB NOT NULL DEFAULT '{}',
    desired_version BIGINT NOT NULL DEFAULT 0,
    desired_at TIMESTAMP WITH TIME ZONE,
    desired_by VARCHAR(128),
    
    -- 已报告状态（设备上报）
    reported JSONB NOT NULL DEFAULT '{}',
    reported_version BIGINT NOT NULL DEFAULT 0,
    reported_at TIMESTAMP WITH TIME ZONE,
    
    -- 标签（云端管理）
    tags JSONB NOT NULL DEFAULT '{}',
    
    -- 元数据
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 约束
    CONSTRAINT valid_device_id CHECK (device_id ~ '^[A-Za-z0-9_-]+$')
);

-- 状态变更历史（审计追踪）
CREATE TABLE twin_change_logs (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL REFERENCES device_twins(device_id) ON DELETE CASCADE,
    
    -- 变更详情
    change_type VARCHAR(16) NOT NULL,  -- 'desired' | 'reported'
    old_value JSONB,
    new_value JSONB,
    
    -- 变更来源
    changed_by VARCHAR(128),           -- 用户ID 或 'device'
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 索引优化
    CONSTRAINT valid_change_type CHECK (change_type IN ('desired', 'reported'))
);

-- 索引
CREATE INDEX idx_twins_desired_at ON device_twins(desired_at DESC);
CREATE INDEX idx_twins_reported_at ON device_twins(reported_at DESC);
CREATE INDEX idx_twins_tags ON device_twins USING GIN(tags);
CREATE INDEX idx_change_logs_device ON twin_change_logs(device_id, changed_at DESC);

-- 自动更新 updated_at
CREATE OR REPLACE FUNCTION update_twin_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER twin_updated
    BEFORE UPDATE ON device_twins
    FOR EACH ROW
    EXECUTE FUNCTION update_twin_timestamp();
```

#### Redis（热数据缓存）

```
# Key 设计
twin:{device_id}:desired     -> JSON (期望状态)
twin:{device_id}:reported    -> JSON (已报告状态)
twin:{device_id}:delta       -> JSON (差异，自动计算)
twin:{device_id}:version     -> Hash {desired_v, reported_v}

# 连接状态
twin:{device_id}:connected   -> 1/0 (设备在线状态)
twin:{device_id}:last_seen   -> Timestamp (最后心跳)

# TTL 策略
- 状态数据：无 TTL（长期存储）
- 连接状态：TTL 300s（5分钟无心跳自动过期）
```

### 3.2 Agent 端本地存储

#### 文件格式（JSON）

```json
// /var/lib/agent/twin.json
{
  "deviceId": "HTCU-开发板-001",
  "desired": {
    "version": 5,
    "data": {
      "firmware": {...},
      "config": {...}
    },
    "receivedAt": "2026-03-11T12:00:00Z"
  },
  "reported": {
    "version": 5,
    "data": {
      "firmware": {...},
      "config": {...},
      "system": {...}
    },
    "reportedAt": "2026-03-11T12:30:00Z"
  },
  "pending": {
    // 待执行的 delta（本地持久化，断电恢复）
    "firmware": {...},
    "config": {...}
  }
}
```

#### 内存结构（C）

```c
// twin_state.h

#ifndef TWIN_STATE_H
#define TWIN_STATE_H

#include <stdint.h>
#include <stdbool.h>
#include "cJSON.h"

// 版本号类型
typedef uint64_t twin_version_t;

// Twin 状态结构
typedef struct {
    char device_id[64];
    
    // 期望状态
    cJSON* desired;              // JSON 对象
    twin_version_t desired_version;
    uint64_t desired_timestamp;  // Unix timestamp (ms)
    
    // 已报告状态
    cJSON* reported;
    twin_version_t reported_version;
    uint64_t reported_timestamp;
    
    // 差异（本地计算）
    cJSON* delta;
    
    // 同步状态
    bool sync_in_progress;       // 是否正在同步
    bool pending_changes;        // 是否有待同步的变更
    
    // 回调函数
    void (*on_delta_changed)(cJSON* delta);
    void (*on_sync_complete)(void);
    
} twin_state_t;

// 初始化/销毁
int twin_init(twin_state_t* state, const char* device_id);
void twin_destroy(twin_state_t* state);

// 加载/保存到文件
int twin_load(twin_state_t* state, const char* filepath);
int twin_save(twin_state_t* state, const char* filepath);

// 状态操作
int twin_set_desired(twin_state_t* state, cJSON* desired, twin_version_t version);
int twin_update_reported(twin_state_t* state, cJSON* partial);
int twin_recalculate_delta(twin_state_t* state);

// 获取差异（用于同步）
cJSON* twin_get_delta(const twin_state_t* state);
bool twin_has_pending_changes(const twin_state_t* state);

#endif // TWIN_STATE_H
```

---

## 4. Agent 端实现

### 4.1 核心模块结构

```
agent/src/
├── twin/
│   ├── twin_state.c          # 状态管理核心
│   ├── twin_sync.c           # 同步协议
│   ├── twin_persist.c        # 本地持久化
│   ├── twin_handler.c        # 业务处理
│   └── twin_diff.c           # 差异计算
└── transport/
    ├── twin_mqtt.c           # MQTT 传输
    └── twin_tcp.c            # TCP 传输（备用）
```

### 4.2 状态管理实现

```c
// twin_state.c

#include "twin_state.h"
#include <string.h>
#include <time.h>

// 计算差异（desired 与 reported 的差集）
static cJSON* compute_delta(cJSON* desired, cJSON* reported) {
    if (!desired) return NULL;
    if (!reported) return cJSON_Duplicate(desired, 1);
    
    cJSON* delta = cJSON_CreateObject();
    
    cJSON* item = NULL;
    cJSON_ArrayForEach(item, desired) {
        const char* key = item->string;
        cJSON* reported_item = cJSON_GetObjectItem(reported, key);
        
        if (!reported_item) {
            // reported 中不存在，加入 delta
            cJSON_AddItemReferenceToObject(delta, key, item);
        } else if (!cJSON_Compare(item, reported_item, 1)) {
            // 值不同，递归比较（支持嵌套对象）
            if (cJSON_IsObject(item) && cJSON_IsObject(reported_item)) {
                cJSON* nested_delta = compute_delta(item, reported_item);
                if (nested_delta && cJSON_GetArraySize(nested_delta) > 0) {
                    cJSON_AddItemToObject(delta, key, nested_delta);
                } else if (nested_delta) {
                    cJSON_Delete(nested_delta);
                }
            } else {
                cJSON_AddItemReferenceToObject(delta, key, item);
            }
        }
    }
    
    return delta;
}

int twin_init(twin_state_t* state, const char* device_id) {
    if (!state || !device_id) return -1;
    
    memset(state, 0, sizeof(twin_state_t));
    strncpy(state->device_id, device_id, sizeof(state->device_id) - 1);
    
    state->desired = cJSON_CreateObject();
    state->reported = cJSON_CreateObject();
    state->delta = cJSON_CreateObject();
    
    return 0;
}

void twin_destroy(twin_state_t* state) {
    if (!state) return;
    
    if (state->desired) cJSON_Delete(state->desired);
    if (state->reported) cJSON_Delete(state->reported);
    if (state->delta) cJSON_Delete(state->delta);
    
    memset(state, 0, sizeof(twin_state_t));
}

int twin_set_desired(twin_state_t* state, cJSON* desired, twin_version_t version) {
    if (!state || !desired) return -1;
    
    // 版本检查（防止旧消息覆盖新状态）
    if (version <= state->desired_version) {
        return 0;  // 忽略旧版本
    }
    
    // 替换 desired
    if (state->desired) cJSON_Delete(state->desired);
    state->desired = cJSON_Duplicate(desired, 1);
    state->desired_version = version;
    state->desired_timestamp = (uint64_t)time(NULL) * 1000;
    
    // 重新计算 delta
    twin_recalculate_delta(state);
    
    // 触发回调
    if (state->on_delta_changed && cJSON_GetArraySize(state->delta) > 0) {
        state->on_delta_changed(state->delta);
    }
    
    return 0;
}

int twin_update_reported(twin_state_t* state, cJSON* partial) {
    if (!state || !partial) return -1;
    
    // 合并到 reported（部分更新）
    cJSON* item = NULL;
    cJSON_ArrayForEach(item, partial) {
        // 移除旧值，添加新值
        cJSON_DeleteItemFromObject(state->reported, item->string);
        cJSON_AddItemReferenceToObject(state->reported, item->string, item);
    }
    
    state->reported_version++;
    state->reported_timestamp = (uint64_t)time(NULL) * 1000;
    
    // 重新计算 delta
    twin_recalculate_delta(state);
    
    // 标记需要同步
    state->pending_changes = true;
    
    return 0;
}

int twin_recalculate_delta(twin_state_t* state) {
    if (!state) return -1;
    
    cJSON* new_delta = compute_delta(state->desired, state->reported);
    
    if (state->delta) cJSON_Delete(state->delta);
    state->delta = new_delta;
    
    return 0;
}
```

### 4.3 同步协议实现

```c
// twin_sync.c

#include "twin_sync.h"
#include "mqtt_client.h"
#include <stdio.h>

// MQTT Topic 设计
#define TOPIC_PREFIX "twin"
#define TOPIC_DESIRED_FMT   TOPIC_PREFIX "/%s/desired"
#define TOPIC_REPORTED_FMT  TOPIC_PREFIX "/%s/reported"
#define TOPIC_DELTA_FMT     TOPIC_PREFIX "/%s/delta"

typedef struct {
    twin_state_t* state;
    mqtt_client_t* mqtt;
    char topic_desired[128];
    char topic_reported[128];
    char topic_delta[128];
    char topic_cmd[128];
} twin_sync_ctx_t;

static twin_sync_ctx_t g_sync_ctx;

// MQTT 消息回调
static void on_mqtt_message(const char* topic, const void* payload, size_t len) {
    twin_sync_ctx_t* ctx = &g_sync_ctx;
    
    if (strstr(topic, "/desired")) {
        // 收到新的期望状态
        cJSON* desired = cJSON_ParseWithLength(payload, len);
        if (desired) {
            cJSON* version_obj = cJSON_GetObjectItem(desired, "$version");
            twin_version_t version = version_obj ? version_obj->valueint : 0;
            
            cJSON* data = cJSON_GetObjectItem(desired, "data");
            if (data) {
                twin_set_desired(ctx->state, data, version);
            }
            
            cJSON_Delete(desired);
            
            // 持久化
            twin_save(ctx->state, "/var/lib/agent/twin.json");
        }
    }
}

// Delta 变化回调（触发业务处理）
static void on_delta_changed(cJSON* delta) {
    twin_sync_ctx_t* ctx = &g_sync_ctx;
    
    // 1. 处理固件更新
    cJSON* firmware = cJSON_GetObjectItem(delta, "firmware");
    if (firmware) {
        // 调用 OTA 模块
        agent_ota_handle_twin(firmware);
    }
    
    // 2. 处理配置变更
    cJSON* config = cJSON_GetObjectItem(delta, "config");
    if (config) {
        // 调用配置模块
        agent_config_apply_twin(config);
        
        // 配置应用成功，更新 reported
        cJSON* reported_update = cJSON_CreateObject();
        cJSON_AddItemReferenceToObject(reported_update, "config", config);
        twin_update_reported(ctx->state, reported_update);
        cJSON_Delete(reported_update);
    }
    
    // 3. 上报新的 reported
    twin_sync_report(ctx);
}

int twin_sync_init(twin_state_t* state, mqtt_client_t* mqtt, const char* device_id) {
    twin_sync_ctx_t* ctx = &g_sync_ctx;
    
    ctx->state = state;
    ctx->mqtt = mqtt;
    
    // 生成 topic
    snprintf(ctx->topic_desired, sizeof(ctx->topic_desired), 
             TOPIC_DESIRED_FMT, device_id);
    snprintf(ctx->topic_reported, sizeof(ctx->topic_reported), 
             TOPIC_REPORTED_FMT, device_id);
    snprintf(ctx->topic_delta, sizeof(ctx->topic_delta), 
             TOPIC_DELTA_FMT, device_id);
    
    // 订阅 desired
    mqtt_subscribe(mqtt, ctx->topic_desired, 1);  // QoS 1
    
    // 设置回调
    state->on_delta_changed = on_delta_changed;
    
    return 0;
}

int twin_sync_report(twin_sync_ctx_t* ctx) {
    if (!ctx || !ctx->state || !ctx->mqtt) return -1;
    
    // 构建 reported 消息
    cJSON* msg = cJSON_CreateObject();
    cJSON_AddNumberToObject(msg, "$version", ctx->state->reported_version);
    cJSON_AddItemReferenceToObject(msg, "data", ctx->state->reported);
    
    char* payload = cJSON_PrintUnformatted(msg);
    
    // 发布到 MQTT (QoS 1)
    int ret = mqtt_publish(ctx->mqtt, ctx->topic_reported, 
                           payload, strlen(payload), 1);
    
    free(payload);
    cJSON_Delete(msg);
    
    if (ret == 0) {
        ctx->state->pending_changes = false;
    }
    
    return ret;
}

// 启动时全量同步
int twin_sync_full(twin_sync_ctx_t* ctx) {
    // 1. 上报当前 reported
    twin_sync_report(ctx);
    
    // 2. 请求完整 desired（通过特殊 topic）
    cJSON* request = cJSON_CreateObject();
    cJSON_AddStringToObject(request, "action", "getDesired");
    char* payload = cJSON_PrintUnformatted(request);
    
    // 发布请求
    char request_topic[128];
    snprintf(request_topic, sizeof(request_topic), 
             TOPIC_PREFIX "/%s/cmd", ctx->state->device_id);
    mqtt_publish(ctx->mqtt, request_topic, payload, strlen(payload), 1);
    
    free(payload);
    cJSON_Delete(request);
    
    return 0;
}
```

### 4.4 业务处理集成

```c
// twin_handler.c

#include "twin_handler.h"
#include "twin_state.h"
#include "agent_ota.h"
#include "agent_config.h"
#include "agent_log.h"

// 处理固件更新
int agent_ota_handle_twin(cJSON* firmware) {
    if (!firmware) return -1;
    
    cJSON* version = cJSON_GetObjectItem(firmware, "version");
    cJSON* url = cJSON_GetObjectItem(firmware, "url");
    cJSON* checksum = cJSON_GetObjectItem(firmware, "checksum");
    
    if (!version || !url) {
        log_error("Invalid firmware twin data");
        return -1;
    }
    
    // 检查是否需要更新
    const char* current_version = agent_ota_get_current_version();
    if (strcmp(current_version, version->valuestring) == 0) {
        log_info("Firmware already at version %s", version->valuestring);
        return 0;  // 无需更新
    }
    
    log_info("Starting OTA update to version %s", version->valuestring);
    
    // 启动下载
    int ret = agent_ota_download(url->valuestring, checksum ? checksum->valuestring : NULL);
    
    if (ret == 0) {
        // 更新进行中，状态会在下载完成后由 OTA 模块更新 reported
        log_info("OTA download started");
    } else {
        log_error("OTA download failed: %d", ret);
    }
    
    return ret;
}

// 处理配置变更
int agent_config_apply_twin(cJSON* config) {
    if (!config) return -1;
    
    // 应用每个配置项
    cJSON* item = NULL;
    cJSON_ArrayForEach(item, config) {
        const char* key = item->string;
        
        if (strcmp(key, "sampleRate") == 0) {
            if (cJSON_IsNumber(item)) {
                agent_config_set_sample_rate(item->valueint);
            }
        }
        else if (strcmp(key, "logLevel") == 0) {
            if (cJSON_IsString(item)) {
                agent_log_set_level(item->valuestring);
            }
        }
        else if (strcmp(key, "network") == 0) {
            cJSON* heartbeat = cJSON_GetObjectItem(item, "heartbeatInterval");
            if (heartbeat && cJSON_IsNumber(heartbeat)) {
                agent_config_set_heartbeat_interval(heartbeat->valueint);
            }
        }
    }
    
    return 0;
}

// OTA 完成回调（由 OTA 模块调用）
void agent_ota_on_complete(int success, const char* version) {
    twin_state_t* state = twin_get_global_state();
    
    cJSON* firmware = cJSON_CreateObject();
    cJSON_AddStringToObject(firmware, "version", version);
    cJSON_AddStringToObject(firmware, "status", success ? "installed" : "failed");
    cJSON_AddNumberToObject(firmware, "installedAt", time(NULL));
    
    cJSON* reported_update = cJSON_CreateObject();
    cJSON_AddItemToObject(reported_update, "firmware", firmware);
    
    twin_update_reported(state, reported_update);
    
    cJSON_Delete(reported_update);
    
    // 立即同步到云端
    twin_sync_report(&g_sync_ctx);
}
```

### 4.5 主循环集成

```c
// agent_main.c (修改)

#include "twin_state.h"
#include "twin_sync.h"

static twin_state_t g_twin_state;

int main(int argc, char** argv) {
    // ... 现有初始化代码 ...
    
    // 1. 初始化 Twin 状态
    twin_init(&g_twin_state, config.device_id);
    
    // 2. 加载本地持久化状态
    twin_load(&g_twin_state, "/var/lib/agent/twin.json");
    
    // 3. 连接 MQTT
    mqtt_client_t* mqtt = mqtt_connect(config.mqtt_url);
    
    // 4. 初始化 Twin 同步
    twin_sync_init(&g_twin_state, mqtt, config.device_id);
    
    // 5. 全量同步（上线时）
    twin_sync_full(&g_sync_ctx);
    
    // 6. 主循环
    while (running) {
        // MQTT 消息处理
        mqtt_loop(mqtt, 100);  // 100ms timeout
        
        // 现有 TCP 处理（保持不变）
        tcp_loop(tcp_client, 100);
        
        // 定期上报系统状态
        if (should_report_metrics()) {
            report_system_metrics(&g_twin_state);
        }
        
        // 定期保存状态
        if (should_save_state()) {
            twin_save(&g_twin_state, "/var/lib/agent/twin.json");
        }
    }
    
    // 清理
    twin_save(&g_twin_state, "/var/lib/agent/twin.json");
    twin_destroy(&g_twin_state);
    
    return 0;
}

// 定期上报系统状态
static void report_system_metrics(twin_state_t* state) {
    cJSON* system = cJSON_CreateObject();
    
    // 采集系统指标
    cJSON_AddNumberToObject(system, "cpuUsage", get_cpu_usage());
    cJSON_AddNumberToObject(system, "memFree", get_free_memory());
    cJSON_AddNumberToObject(system, "uptime", get_uptime());
    
    // 更新 reported
    cJSON* reported_update = cJSON_CreateObject();
    cJSON_AddItemToObject(reported_update, "system", system);
    
    twin_update_reported(state, reported_update);
    cJSON_Delete(reported_update);
}
```

---

## 5. Server 端实现

### 5.1 API 设计

#### RESTful API

```yaml
# OpenAPI 3.0 规范

paths:
  # 获取设备 Twin
  /api/v1/devices/{deviceId}/twin:
    get:
      summary: 获取设备 Twin
      parameters:
        - name: deviceId
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DeviceTwin'
    
    # 更新期望状态
    patch:
      summary: 更新期望状态
      parameters:
        - name: deviceId
          in: path
          required: true
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                desired:
                  type: object
      responses:
        200:
          description: 更新成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DeviceTwin'
        409:
          description: 版本冲突

  # 批量操作
  /api/v1/twins/batch:
    post:
      summary: 批量更新期望状态
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                deviceIds:
                  type: array
                  items:
                    type: string
                desired:
                  type: object
                filters:
                  type: object
                  description: 按标签筛选设备
      responses:
        202:
          description: 已接受，异步处理

  # 查询历史
  /api/v1/devices/{deviceId}/twin/history:
    get:
      summary: 获取状态变更历史
      parameters:
        - name: deviceId
          in: path
        - name: from
          in: query
          schema:
            type: string
            format: date-time
        - name: to
          in: query
          schema:
            type: string
            format: date-time
        - name: type
          in: query
          schema:
            type: string
            enum: [desired, reported]
      responses:
        200:
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/ChangeLog'

components:
  schemas:
    DeviceTwin:
      type: object
      properties:
        deviceId:
          type: string
        desired:
          type: object
        desiredVersion:
          type: integer
        reported:
          type: object
        reportedVersion:
          type: integer
        delta:
          type: object
        tags:
          type: object
        metadata:
          type: object
          
    ChangeLog:
      type: object
      properties:
        changeType:
          type: string
        oldValue:
          type: object
        newValue:
          type: object
        changedAt:
          type: string
          format: date-time
        changedBy:
          type: string
```

### 5.2 Server 端实现（Python）

```python
# twin_service.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import json
import asyncpg
import redis.asyncio as redis
from pydantic import BaseModel

class TwinData(BaseModel):
    desired: Dict[str, Any] = {}
    desired_version: int = 0
    desired_at: Optional[datetime] = None
    desired_by: Optional[str] = None
    
    reported: Dict[str, Any] = {}
    reported_version: int = 0
    reported_at: Optional[datetime] = None
    
    tags: Dict[str, Any] = {}

@dataclass
class DeviceTwin:
    device_id: str
    desired: dict
    desired_version: int
    reported: dict
    reported_version: int
    tags: dict
    
    @property
    def delta(self) -> dict:
        """计算 desired 与 reported 的差异"""
        return self._compute_delta(self.desired, self.reported)
    
    @staticmethod
    def _compute_delta(desired: dict, reported: dict) -> dict:
        """递归计算差异"""
        delta = {}
        for key, desired_value in desired.items():
            if key not in reported:
                delta[key] = desired_value
            elif isinstance(desired_value, dict) and isinstance(reported.get(key), dict):
                nested = DeviceTwin._compute_delta(desired_value, reported[key])
                if nested:
                    delta[key] = nested
            elif desired_value != reported.get(key):
                delta[key] = desired_value
        return delta


class TwinService:
    def __init__(self, pg_pool: asyncpg.Pool, redis_client: redis.Redis):
        self.pg = pg_pool
        self.redis = redis_client
    
    async def get_twin(self, device_id: str) -> Optional[DeviceTwin]:
        """获取设备 Twin（优先从 Redis 缓存）"""
        
        # 1. 尝试从 Redis 获取
        cache_key = f"twin:{device_id}"
        cached = await self.redis.hgetall(cache_key)
        
        if cached:
            return DeviceTwin(
                device_id=device_id,
                desired=json.loads(cached.get(b'desired', b'{}')),
                desired_version=int(cached.get(b'desired_version', 0)),
                reported=json.loads(cached.get(b'reported', b'{}')),
                reported_version=int(cached.get(b'reported_version', 0)),
                tags=json.loads(cached.get(b'tags', b'{}')),
            )
        
        # 2. 从 PostgreSQL 加载
        row = await self.pg.fetchrow(
            """
            SELECT desired, desired_version, reported, reported_version, tags
            FROM device_twins
            WHERE device_id = $1
            """,
            device_id
        )
        
        if not row:
            # 设备不存在，创建默认 Twin
            await self._create_default_twin(device_id)
            return DeviceTwin(
                device_id=device_id,
                desired={},
                desired_version=0,
                reported={},
                reported_version=0,
                tags={},
            )
        
        twin = DeviceTwin(
            device_id=device_id,
            desired=row['desired'],
            desired_version=row['desired_version'],
            reported=row['reported'],
            reported_version=row['reported_version'],
            tags=row['tags'],
        )
        
        # 3. 写入 Redis 缓存
        await self._cache_twin(twin)
        
        return twin
    
    async def update_desired(
        self, 
        device_id: str, 
        desired: dict,
        updated_by: str
    ) -> DeviceTwin:
        """更新期望状态"""
        
        # 1. 获取当前 Twin
        twin = await self.get_twin(device_id)
        
        # 2. 合并 desired（部分更新）
        new_desired = {**twin.desired, **desired}
        new_version = twin.desired_version + 1
        
        # 3. 更新 PostgreSQL
        await self.pg.execute(
            """
            UPDATE device_twins
            SET desired = $2,
                desired_version = $3,
                desired_at = NOW(),
                desired_by = $4
            WHERE device_id = $1
            """,
            device_id, json.dumps(new_desired), new_version, updated_by
        )
        
        # 4. 记录变更历史
        await self._log_change(
            device_id, 'desired', 
            twin.desired, new_desired, 
            updated_by
        )
        
        # 5. 更新 Redis 缓存
        twin.desired = new_desired
        twin.desired_version = new_version
        await self._cache_twin(twin)
        
        # 6. 推送到 MQTT（如果设备在线）
        await self._push_desired_to_device(device_id, new_desired, new_version)
        
        return twin
    
    async def update_reported(
        self,
        device_id: str,
        reported: dict,
        version: int
    ) -> DeviceTwin:
        """处理设备上报的状态"""
        
        # 1. 获取当前 Twin
        twin = await self.get_twin(device_id)
        
        # 2. 版本检查（乐观锁）
        if version <= twin.reported_version:
            # 忽略旧版本
            return twin
        
        # 3. 合并 reported
        new_reported = {**twin.reported, **reported}
        
        # 4. 更新数据库
        await self.pg.execute(
            """
            UPDATE device_twins
            SET reported = $2,
                reported_version = $3,
                reported_at = NOW()
            WHERE device_id = $1
            """,
            device_id, json.dumps(new_reported), version
        )
        
        # 5. 记录变更
        await self._log_change(
            device_id, 'reported',
            twin.reported, new_reported,
            'device'
        )
        
        # 6. 更新缓存
        twin.reported = new_reported
        twin.reported_version = version
        await self._cache_twin(twin)
        
        # 7. 检查 delta 是否变化，通知 WebSocket 客户端
        await self._notify_web_clients(device_id, twin)
        
        return twin
    
    async def _cache_twin(self, twin: DeviceTwin):
        """写入 Redis 缓存"""
        cache_key = f"twin:{twin.device_id}"
        
        await self.redis.hset(cache_key, mapping={
            'desired': json.dumps(twin.desired),
            'desired_version': twin.desired_version,
            'reported': json.dumps(twin.reported),
            'reported_version': twin.reported_version,
            'tags': json.dumps(twin.tags),
        })
    
    async def _push_desired_to_device(
        self, 
        device_id: str, 
        desired: dict, 
        version: int
    ):
        """通过 MQTT 推送到设备"""
        
        # 检查设备是否在线
        connected = await self.redis.get(f"twin:{device_id}:connected")
        if not connected:
            return  # 设备离线，等上线后拉取
        
        # 构建消息
        message = {
            "$version": version,
            "data": desired
        }
        
        # 发布到 MQTT
        topic = f"twin/{device_id}/desired"
        await self.mqtt_publish(topic, json.dumps(message), qos=1)
    
    async def _log_change(
        self,
        device_id: str,
        change_type: str,
        old_value: dict,
        new_value: dict,
        changed_by: str
    ):
        """记录变更历史"""
        await self.pg.execute(
            """
            INSERT INTO twin_change_logs 
            (device_id, change_type, old_value, new_value, changed_by)
            VALUES ($1, $2, $3, $4, $5)
            """,
            device_id, change_type,
            json.dumps(old_value), json.dumps(new_value),
            changed_by
        )
    
    async def _notify_web_clients(self, device_id: str, twin: DeviceTwin):
        """通知 WebSocket 客户端"""
        # 通过 WebSocket 推送 delta 变化
        await self.ws_broadcast(f"twin:{device_id}", {
            "type": "twin_updated",
            "deviceId": device_id,
            "delta": twin.delta,
            "reported": twin.reported,
        })
```

### 5.3 MQTT 消息处理

```python
# mqtt_handler.py

import json
from twin_service import TwinService

class TwinMqttHandler:
    def __init__(self, twin_service: TwinService):
        self.twin = twin_service
    
    async def on_message(self, topic: str, payload: bytes):
        """处理 MQTT 消息"""
        
        # 解析 topic
        # twin/{device_id}/reported
        parts = topic.split('/')
        
        if len(parts) != 3:
            return
        
        prefix, device_id, msg_type = parts
        
        if prefix != 'twin':
            return
        
        # 处理设备上报
        if msg_type == 'reported':
            data = json.loads(payload)
            version = data.get('$version', 0)
            reported = data.get('data', {})
            
            await self.twin.update_reported(device_id, reported, version)
        
        # 处理设备请求完整 desired
        elif msg_type == 'cmd':
            data = json.loads(payload)
            if data.get('action') == 'getDesired':
                twin = await self.twin.get_twin(device_id)
                await self._send_desired(device_id, twin)
    
    async def _send_desired(self, device_id: str, twin):
        """发送完整 desired 到设备"""
        message = {
            "$version": twin.desired_version,
            "data": twin.desired
        }
        await self.mqtt_publish(
            f"twin/{device_id}/desired",
            json.dumps(message),
            qos=1
        )
    
    async def on_device_connected(self, device_id: str):
        """设备上线时调用"""
        # 设置在线状态
        await self.redis.set(f"twin:{device_id}:connected", "1", ex=300)
        
        # 发送完整 desired（设备可能错过离线期间的消息）
        twin = await self.twin.get_twin(device_id)
        await self._send_desired(device_id, twin)
    
    async def on_device_disconnected(self, device_id: str):
        """设备离线时调用"""
        await self.redis.delete(f"twin:{device_id}:connected")
```

---

## 6. 同步协议

### 6.1 MQTT Topic 设计

```
twin/{device_id}/desired     # 云端 → 设备（期望状态）
twin/{device_id}/reported    # 设备 → 云端（已报告状态）
twin/{device_id}/cmd         # 设备 → 云端（命令请求）
twin/{device_id}/ack         # 云端 → 设备（确认响应）
```

### 6.2 消息格式

#### Desired 消息（云端 → 设备）

```json
{
  "$version": 5,
  "$timestamp": "2026-03-11T12:00:00Z",
  "data": {
    "firmware": {
      "version": "2.1.0",
      "url": "https://..."
    },
    "config": {
      "sampleRate": 1000
    }
  }
}
```

#### Reported 消息（设备 → 云端）

```json
{
  "$version": 5,
  "$timestamp": "2026-03-11T12:30:00Z",
  "data": {
    "firmware": {
      "version": "2.1.0",
      "installedAt": "2026-03-11T12:15:00Z"
    },
    "config": {
      "sampleRate": 1000
    },
    "system": {
      "cpuUsage": 23.5
    }
  }
}
```

### 6.3 同步流程

```
┌─────────┐                              ┌─────────┐                    ┌─────────┐
│  Agent  │                              │   MQTT  │                    │  Server │
└────┬────┘                              └────┬────┘                    └────┬────┘
     │                                        │                              │
     │  1. 连接成功                            │                              │
     ├───────────────────────────────────────>│                              │
     │                                        │                              │
     │  2. 订阅 twin/{id}/desired             │                              │
     ├───────────────────────────────────────>│                              │
     │                                        │                              │
     │  3. 上报当前 reported                   │                              │
     │    (twin/{id}/reported)                │                              │
     ├───────────────────────────────────────>│──────────────────────────────>│
     │                                        │                              │
     │  4. 请求完整 desired                    │                              │
     │    (twin/{id}/cmd, action=getDesired)  │                              │
     ├───────────────────────────────────────>│──────────────────────────────>│
     │                                        │                              │
     │                                        │  5. 返回完整 desired           │
     │<───────────────────────────────────────│<──────────────────────────────┤
     │                                        │                              │
     │  6. 执行 delta（如固件更新）             │                              │
     │                                        │                              │
     │  7. 更新成功，上报 reported             │                              │
     ├───────────────────────────────────────>│──────────────────────────────>│
     │                                        │                              │
     │                                        │                              │
     │  === 正常运行期间 ===                    │                              │
     │                                        │                              │
     │                                        │  8. 云端修改 desired           │
     │<───────────────────────────────────────│<──────────────────────────────┤
     │                                        │                              │
     │  9. 执行 delta，上报 reported           │                              │
     ├───────────────────────────────────────>│──────────────────────────────>│
     │                                        │                              │
     │  10. 定期上报系统状态                    │                              │
     ├───────────────────────────────────────>│──────────────────────────────>│
     │                                        │                              │
```

### 6.4 版本控制与冲突解决

**规则**：
1. 每次修改 desired/reported，版本号 +1
2. 设备忽略版本号 ≤ 当前版本的消息
3. 云端使用乐观锁，检查 reported_version 防止覆盖

**冲突场景**：

```
场景：云端和设备同时修改

时间线：
T1: 云端修改 desired (version 5 → 6)
T2: 设备上报 reported (version 5)  ← 网络延迟
T3: 云端收到设备上报，检查 version

处理：
- 如果 reported.version > 云端记录的 version：接受
- 如果 reported.version <= 云端记录的 version：接受（设备可能没收到新的 desired）
- 总是合并，不覆盖
```

---

## 7. 边界情况处理

### 7.1 设备离线

| 场景 | 处理方式 |
|------|----------|
| 云端修改 desired | 存入数据库，设备上线后推送 |
| 查询设备状态 | 返回最后的 reported（带时间戳说明） |
| 多次修改 desired | 只保留最新版本，历史存入 change_logs |

### 7.2 网络抖动

| 场景 | 处理方式 |
|------|----------|
| MQTT QoS | 使用 QoS 1，保证至少投递一次 |
| 消息重复 | 设备通过 version 去重 |
| 顺序问题 | MQTT 保证同一 topic 的消息顺序 |

### 7.3 并发修改

```
场景：两个管理员同时修改 desired

处理：使用 PostgreSQL 事务 + 乐观锁

BEGIN;
SELECT desired_version FROM device_twins WHERE device_id = $1 FOR UPDATE;
-- 检查版本
-- 如果版本匹配，更新
UPDATE device_twins SET desired = $2, desired_version = desired_version + 1 ...;
COMMIT;

如果版本不匹配，返回 409 Conflict，客户端重试
```

### 7.4 大状态对象

**问题**：某些配置可能很大（如白名单 10000 条）

**解决方案**：
1. 分层存储：大对象存入 S3，Twin 只存 URL
2. 增量更新：支持 JSON Patch 格式

```json
{
  "$version": 6,
  "patch": [
    {"op": "replace", "path": "/config/whitelistUrl", "value": "https://..."}
  ]
}
```

### 7.5 设备固件不支持 Twin

**兼容策略**：
- Agent 版本协商：注册时上报 `twin_version`
- 老设备（twin_version = 0 或不存在）：继续使用 TCP 命令模式
- 新设备：启用 Twin 模式

---

## 8. 与现有系统兼容

### 8.1 共存策略

```
┌─────────────────────────────────────────────────────────────┐
│                         Agent                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────────────┐     ┌─────────────────────┐      │
│   │   Twin 模块 (新)     │     │  现有 TCP 模块       │      │
│   │   - 配置管理         │     │  - PTY 终端         │      │
│   │   - 固件更新         │     │  - 文件传输         │      │
│   │   - 状态上报         │     │  - 实时命令         │      │
│   └──────────┬──────────┘     └──────────┬──────────┘      │
│              │                            │                  │
│              ▼                            ▼                  │
│         ┌─────────┐                  ┌─────────┐            │
│         │  MQTT   │                  │   TCP   │            │
│         └─────────┘                  └─────────┘            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 功能映射

| 功能 | 现有方式 (TCP) | 新方式 (Twin) | 迁移策略 |
|------|---------------|---------------|----------|
| 心跳 | HEARTBEAT (0x01) | MQTT 遗嘱消息 | 保持 TCP，MQTT 作为备用 |
| 状态上报 | SYSTEM_STATUS (0x02) | Twin reported | 迁移到 Twin |
| 配置下发 | SCRIPT_RECV (0x04) | Twin desired | 迁移到 Twin |
| OTA 更新 | UPDATE_* (0x60-0x6B) | Twin desired + 命令 | 混合模式 |
| PTY 终端 | PTY_* (0x10-0x13) | 保持 TCP | 不迁移 |
| 文件传输 | FILE_* (0x20-0x27) | 保持 TCP | 不迁移 |

### 8.3 消息类型扩展

在现有协议基础上增加 Twin 相关消息类型：

| 类型 | 十六进制 | 名称 | 方向 | 说明 |
|------|---------|------|------|------|
| TWIN_DESIRED | 0x70 | Twin期望 | Server→Client | 通过 TCP 下发 Twin（备用通道） |
| TWIN_REPORTED | 0x71 | Twin上报 | Client→Server | 通过 TCP 上报 Twin（备用通道） |

这些消息用于 MQTT 不可用时，通过 TCP 进行 Twin 同步。

---

## 9. 迁移路径

### 9.1 阶段规划

```
Phase 1: 基础设施（2 周）
├── 搭建 MQTT Broker (EMQX)
├── 创建 PostgreSQL 表结构
├── 配置 Redis
└── 部署 Twin Service

Phase 2: Agent 集成（3 周）
├── 实现 Twin 模块 (C 代码)
├── 集成 MQTT 客户端
├── 本地持久化
└── 单元测试

Phase 3: Server 集成（2 周）
├── Twin REST API
├── MQTT 消息处理
├── WebSocket 推送
└── 集成测试

Phase 4: 功能迁移（3 周）
├── 状态上报迁移到 Twin
├── 配置下发迁移到 Twin
├── Web UI 适配
└── 灰度测试

Phase 5: OTA 集成（2 周）
├── OTA 流程对接 Twin
├── 审批流程保留
└── 灰度发布

Phase 6: 监控与优化（持续）
├── 性能监控
├── 告警配置
└── 文档完善
```

### 9.2 灰度策略

```yaml
# 配置示例：按设备标签灰度

twin_rollout:
  enabled: true
  strategy: "tag"
  
  # 灰度标签
  canary_tag: "twin_beta"
  
  # 灰度比例（0.0 - 1.0）
  percentage: 0.1
  
  # 白名单设备
  whitelist:
    - "HTCU-开发板-001"
    - "HTCU-测试板-003"
```

**灰度流程**：
1. Server 检查设备是否在灰度名单
2. 在名单内：使用 Twin 模式
3. 不在名单内：继续使用 TCP 命令模式
4. 逐步扩大灰度比例
5. 全量后移除灰度配置

---

## 10. 测试策略

### 10.1 单元测试

```c
// test_twin_state.c

void test_compute_delta() {
    cJSON* desired = cJSON_Parse("{\"firmware\":{\"version\":\"2.0\"},\"config\":{\"rate\":100}}");
    cJSON* reported = cJSON_Parse("{\"firmware\":{\"version\":\"1.0\"},\"config\":{\"rate\":100}}");
    
    cJSON* delta = compute_delta(desired, reported);
    
    // delta 应该只包含 firmware
    assert(cJSON_HasObjectItem(delta, "firmware"));
    assert(!cJSON_HasObjectItem(delta, "config"));
    
    cJSON_Delete(desired);
    cJSON_Delete(reported);
    cJSON_Delete(delta);
}

void test_version_check() {
    twin_state_t state;
    twin_init(&state, "test-device");
    
    // 设置初始 desired
    cJSON* d1 = cJSON_Parse("{\"config\":{\"rate\":100}}");
    twin_set_desired(&state, d1, 5);
    
    // 尝试用旧版本覆盖
    cJSON* d2 = cJSON_Parse("{\"config\":{\"rate\":200}}");
    int ret = twin_set_desired(&state, d2, 3);  // 版本 3 < 5
    
    // 应该被忽略
    assert(ret == 0);
    assert(state.desired_version == 5);
    
    // 版本相同应该被接受
    ret = twin_set_desired(&state, d2, 6);
    assert(ret == 0);
    assert(state.desired_version == 6);
    
    cJSON_Delete(d1);
    cJSON_Delete(d2);
    twin_destroy(&state);
}
```

### 10.2 集成测试

```python
# test_twin_integration.py

import pytest
import asyncio
from twin_service import TwinService

@pytest.mark.asyncio
async def test_desired_reported_sync():
    """测试 desired 和 reported 同步"""
    
    twin_service = TwinService(pg_pool, redis_client)
    
    # 1. 云端设置 desired
    await twin_service.update_desired(
        "test-device-001",
        {"config": {"sampleRate": 1000}},
        "test-user"
    )
    
    # 2. 设备上报 reported
    await twin_service.update_reported(
        "test-device-001",
        {"config": {"sampleRate": 1000}},
        version=1
    )
    
    # 3. 检查 delta 应该为空
    twin = await twin_service.get_twin("test-device-001")
    assert twin.delta == {}
    
@pytest.mark.asyncio
async def test_offline_device():
    """测试离线设备状态持久化"""
    
    # 1. 设备离线
    await redis_client.delete("twin:test-device-001:connected")
    
    # 2. 云端修改 desired
    await twin_service.update_desired(
        "test-device-001",
        {"firmware": {"version": "2.1.0"}},
        "test-user"
    )
    
    # 3. 模拟设备上线
    await mqtt_handler.on_device_connected("test-device-001")
    
    # 4. 验证设备收到 desired
    # (检查 MQTT 发布记录)
    assert published_messages["twin/test-device-001/desired"]
```

### 10.3 契约测试

```yaml
# contract_test.yaml

# Agent 与 Server 的协议契约

messages:
  - name: DesiredMessage
    direction: server_to_agent
    topic: "twin/{device_id}/desired"
    schema:
      type: object
      required: ["$version", "data"]
      properties:
        $version:
          type: integer
          minimum: 1
        $timestamp:
          type: string
          format: date-time
        data:
          type: object
    
  - name: ReportedMessage
    direction: agent_to_server
    topic: "twin/{device_id}/reported"
    schema:
      type: object
      required: ["$version", "data"]
      properties:
        $version:
          type: integer
          minimum: 1
        $timestamp:
          type: string
          format: date-time
        data:
          type: object

# 测试用例
test_cases:
  - name: "Agent rejects old version desired"
    steps:
      - send:
          message: DesiredMessage
          payload: {"$version": 5, "data": {"config": {"rate": 100}}}
      - send:
          message: DesiredMessage
          payload: {"$version": 3, "data": {"config": {"rate": 200}}}
      - expect:
          agent_state.desired_version: 5
          agent_state.desired.config.rate: 100
```

---

## 附录 A: 术语表

| 术语 | 定义 |
|------|------|
| Device Twin | 设备孪生，设备状态的云端副本 |
| Desired State | 期望状态，云端定义的目标状态 |
| Reported State | 已报告状态，设备实际上报的状态 |
| Delta | 差异，Desired 与 Reported 的差集 |
| Convergence | 收敛，设备执行操作使 Reported 接近 Desired |

## 附录 B: 参考资源

- [Azure IoT Hub Device Twins](https://learn.microsoft.com/en-us/azure/iot-hub/iot-hub-devguide-device-twins)
- [AWS IoT Device Shadow](https://docs.aws.amazon.com/iot/latest/developerguide/iot-device-shadows.html)
- [Eclipse Ditto Digital Twins](https://eclipse.github.io/ditto/introduction-overview.html)
- [MQTT 5.0 Specification](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html)

---

*文档结束*