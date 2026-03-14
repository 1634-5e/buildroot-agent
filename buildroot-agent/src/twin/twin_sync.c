/**
 * @file twin_sync.c
 * @brief Device Twin 同步模块实现
 */

#include "twin/twin_sync.h"
#include "twin/twin_diff.h"
#include <cjson/cJSON.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* ==================== 内部结构 ==================== */

struct twin_sync {
    twin_state_t* state;
    twin_sync_config_t config;
    
    mqtt_client_t* mqtt;
    twin_sync_status_t status;
    
    /* 回调 */
    twin_delta_callback_t delta_callback;
    twin_sync_done_callback_t sync_done_callback;
    
    /* 定时器 */
    uint64_t last_report_time;
    uint64_t last_sync_time;
};

/* ==================== 内部常量 ==================== */

#define DEFAULT_SYNC_INTERVAL    30000    /* 30 秒 */
#define DEFAULT_REPORT_INTERVAL  60000    /* 60 秒 */

/* ==================== 内部函数声明 ==================== */

static void on_mqtt_message(mqtt_client_t* client, const char* topic, 
                           const void* payload, size_t len, void* user_data);
static void on_mqtt_state(mqtt_client_t* client, mqtt_state_t state, void* user_data);
static void on_twin_delta_changed(twin_state_t* state, cJSON* delta);
static uint64_t get_time_ms(void);

/* ==================== 公开函数实现 ==================== */

void twin_sync_get_default_config(twin_sync_config_t* config, const char* device_id) {
    if (!config || !device_id) return;
    
    memset(config, 0, sizeof(twin_sync_config_t));
    
    strncpy(config->device_id, device_id, sizeof(config->device_id) - 1);
    strncpy(config->mqtt_broker, "tcp://localhost:1883", sizeof(config->mqtt_broker) - 1);
    config->mqtt_port = 1883;
    
    /* 生成 Topic */
    snprintf(config->topic_desired, sizeof(config->topic_desired), 
             "twin/%s/desired", device_id);
    snprintf(config->topic_reported, sizeof(config->topic_reported), 
             "twin/%s/reported", device_id);
    snprintf(config->topic_cmd, sizeof(config->topic_cmd), 
             "twin/%s/cmd", device_id);
    
    config->sync_interval = DEFAULT_SYNC_INTERVAL;
    config->report_interval = DEFAULT_REPORT_INTERVAL;
    config->auto_report = true;
}

twin_sync_t* twin_sync_create(twin_state_t* state, const twin_sync_config_t* config) {
    if (!state || !config) return NULL;
    
    twin_sync_t* sync = (twin_sync_t*)calloc(1, sizeof(twin_sync_t));
    if (!sync) return NULL;
    
    sync->state = state;
    memcpy(&sync->config, config, sizeof(twin_sync_config_t));
    sync->status = TWIN_SYNC_IDLE;
    
    /* 设置状态回调 */
    state->on_delta_changed = on_twin_delta_changed;
    
    /* 创建 MQTT 客户端 */
    mqtt_config_t mqtt_config;
    mqtt_client_get_default_config(&mqtt_config);
    
    strncpy(mqtt_config.broker_url, config->mqtt_broker, sizeof(mqtt_config.broker_url) - 1);
    strncpy(mqtt_config.client_id, config->device_id, sizeof(mqtt_config.client_id) - 1);
    
    if (config->mqtt_username[0]) {
        strncpy(mqtt_config.username, config->mqtt_username, sizeof(mqtt_config.username) - 1);
    }
    if (config->mqtt_password[0]) {
        strncpy(mqtt_config.password, config->mqtt_password, sizeof(mqtt_config.password) - 1);
    }
    
    /* 遗嘱消息 */
    snprintf(mqtt_config.will_topic, sizeof(mqtt_config.will_topic), 
             "twin/%s/status", config->device_id);
    snprintf(mqtt_config.will_payload, sizeof(mqtt_config.will_payload), 
             "{\"connected\":false}");
    mqtt_config.will_qos = MQTT_QOS_1;
    mqtt_config.will_retain = true;
    
    mqtt_config.auto_reconnect = true;
    
    sync->mqtt = mqtt_client_create(&mqtt_config);
    if (!sync->mqtt) {
        free(sync);
        return NULL;
    }
    
    /* 设置回调 */
    mqtt_client_set_message_callback(sync->mqtt, on_mqtt_message, sync);
    mqtt_client_set_state_callback(sync->mqtt, on_mqtt_state, sync);
    
    return sync;
}

void twin_sync_destroy(twin_sync_t* sync) {
    if (!sync) return;
    
    if (sync->mqtt) {
        if (mqtt_client_is_connected(sync->mqtt)) {
            /* 发送离线状态 */
            mqtt_client_publish(
                sync->mqtt,
                sync->config.topic_cmd,
                "{\"connected\":false}",
                20,
                MQTT_QOS_1,
                true
            );
            mqtt_client_disconnect(sync->mqtt);
        }
        mqtt_client_destroy(sync->mqtt);
    }
    
    free(sync);
}

int twin_sync_connect(twin_sync_t* sync) {
    if (!sync || !sync->mqtt) return -1;
    
    int ret = mqtt_client_connect(sync->mqtt);
    if (ret != 0) return -1;
    
    /* 订阅 desired */
    ret = mqtt_client_subscribe(sync->mqtt, sync->config.topic_desired, MQTT_QOS_1);
    if (ret != 0) {
        mqtt_client_disconnect(sync->mqtt);
        return -1;
    }
    
    /* 发送在线状态 */
    cJSON* status = cJSON_CreateObject();
    cJSON_AddBoolToObject(status, "connected", true);
    cJSON_AddNumberToObject(status, "timestamp", get_time_ms());
    
    char* status_str = cJSON_PrintUnformatted(status);
    
    char status_topic[128];
    snprintf(status_topic, sizeof(status_topic), 
             "twin/%s/status", sync->config.device_id);
    
    mqtt_client_publish(
        sync->mqtt,
        status_topic,
        status_str,
        strlen(status_str),
        MQTT_QOS_1,
        true
    );
    
    free(status_str);
    cJSON_Delete(status);
    
    /* 执行全量同步 */
    return twin_sync_full(sync);
}

int twin_sync_disconnect(twin_sync_t* sync) {
    if (!sync || !sync->mqtt) return -1;
    return mqtt_client_disconnect(sync->mqtt);
}

bool twin_sync_is_connected(twin_sync_t* sync) {
    if (!sync || !sync->mqtt) return false;
    return mqtt_client_is_connected(sync->mqtt);
}

int twin_sync_full(twin_sync_t* sync) {
    if (!sync || !sync->mqtt) return -1;
    
    sync->status = TWIN_SYNC_IN_PROGRESS;
    
    /* 1. 上报当前 reported */
    int ret = twin_sync_report(sync);
    if (ret != 0) {
        sync->status = TWIN_SYNC_ERROR;
        return -1;
    }
    
    /* 2. 请求完整 desired */
    ret = twin_sync_request_desired(sync);
    if (ret != 0) {
        sync->status = TWIN_SYNC_ERROR;
        return -1;
    }
    
    sync->last_sync_time = get_time_ms();
    sync->status = TWIN_SYNC_IDLE;
    
    if (sync->sync_done_callback) {
        sync->sync_done_callback(sync, true);
    }
    
    return 0;
}

int twin_sync_report(twin_sync_t* sync) {
    if (!sync || !sync->mqtt) return -1;
    
    if (!mqtt_client_is_connected(sync->mqtt)) {
        return -1;
    }
    
    /* 构建消息 */
    cJSON* msg = cJSON_CreateObject();
    cJSON_AddNumberToObject(msg, "$version", sync->state->reported_version);
    cJSON_AddNumberToObject(msg, "$timestamp", get_time_ms());
    cJSON_AddItemReferenceToObject(msg, "data", sync->state->reported);
    
    char* payload = cJSON_PrintUnformatted(msg);
    if (!payload) {
        cJSON_Delete(msg);
        return -1;
    }
    
    /* 发布 */
    int ret = mqtt_client_publish(
        sync->mqtt,
        sync->config.topic_reported,
        payload,
        strlen(payload),
        MQTT_QOS_1,
        false
    );
    
    free(payload);
    cJSON_Delete(msg);
    
    if (ret == 0) {
        sync->last_report_time = get_time_ms();
        sync->state->pending_changes = false;
    }
    
    return ret;
}

int twin_sync_request_desired(twin_sync_t* sync) {
    if (!sync || !sync->mqtt) return -1;
    
    if (!mqtt_client_is_connected(sync->mqtt)) {
        return -1;
    }
    
    /* 构建请求 */
    cJSON* request = cJSON_CreateObject();
    cJSON_AddStringToObject(request, "action", "getDesired");
    cJSON_AddNumberToObject(request, "currentVersion", sync->state->desired_version);
    
    char* payload = cJSON_PrintUnformatted(request);
    if (!payload) {
        cJSON_Delete(request);
        return -1;
    }
    
    /* 发布 */
    int ret = mqtt_client_publish(
        sync->mqtt,
        sync->config.topic_cmd,
        payload,
        strlen(payload),
        MQTT_QOS_1,
        false
    );
    
    free(payload);
    cJSON_Delete(request);
    
    return ret;
}

int twin_sync_loop(twin_sync_t* sync, uint32_t timeout_ms) {
    if (!sync || !sync->mqtt) return -1;
    
    /* 处理 MQTT 事件 */
    mqtt_client_loop(sync->mqtt, timeout_ms);
    
    /* 检查是否需要定期上报 */
    uint64_t now = get_time_ms();
    
    if (sync->config.auto_report && 
        now - sync->last_report_time >= sync->config.report_interval) {
        /* 收集系统状态并上报 */
        cJSON* system = cJSON_CreateObject();
        cJSON_AddNumberToObject(system, "cpuUsage", 0);  /* TODO: 实际采集 */
        cJSON_AddNumberToObject(system, "memFree", 0);
        cJSON_AddNumberToObject(system, "uptime", 0);
        
        cJSON* partial = cJSON_CreateObject();
        cJSON_AddItemToObject(partial, "system", system);
        
        twin_state_update_reported(sync->state, partial);
        cJSON_Delete(partial);
        
        twin_sync_report(sync);
    }
    
    return 0;
}

void twin_sync_set_delta_callback(twin_sync_t* sync, twin_delta_callback_t callback) {
    if (sync) {
        sync->delta_callback = callback;
    }
}

void twin_sync_set_sync_done_callback(twin_sync_t* sync, twin_sync_done_callback_t callback) {
    if (sync) {
        sync->sync_done_callback = callback;
    }
}

twin_sync_status_t twin_sync_get_status(twin_sync_t* sync) {
    if (!sync) return TWIN_SYNC_ERROR;
    return sync->status;
}

/* ==================== 内部函数实现 ==================== */

static void on_mqtt_message(mqtt_client_t* client, const char* topic, 
                           const void* payload, size_t len, void* user_data) {
    twin_sync_t* sync = (twin_sync_t*)user_data;
    
    (void)client;  /* 未使用 */
    
    /* 检查是否是 desired topic */
    if (strstr(topic, "/desired")) {
        /* 解析消息 */
        cJSON* msg = cJSON_ParseWithLength((const char*)payload, len);
        if (!msg) return;
        
        cJSON* version = cJSON_GetObjectItem(msg, "$version");
        cJSON* data = cJSON_GetObjectItem(msg, "data");
        
        if (version && data) {
            /* 更新期望状态 */
            twin_state_set_desired(sync->state, data, version->valueint);
            
            /* 触发回调 */
            if (sync->delta_callback) {
                sync->delta_callback(sync, sync->state->delta);
            }
        }
        
        cJSON_Delete(msg);
    }
}

static void on_mqtt_state(mqtt_client_t* client, mqtt_state_t state, void* user_data) {
    twin_sync_t* sync = (twin_sync_t*)user_data;
    
    (void)client;  /* 未使用 */
    
    if (state == MQTT_STATE_DISCONNECTED) {
        sync->status = TWIN_SYNC_ERROR;
    }
}

static void on_twin_delta_changed(twin_state_t* state, cJSON* delta) {
    /* 当 delta 变化时，由外部处理 */
    (void)state;
    (void)delta;
}

static uint64_t get_time_ms(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_REALTIME, &ts) != 0) {
        return 0;
    }
    return (uint64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}