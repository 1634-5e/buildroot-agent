/**
 * @file agent_twin.c
 * @brief Device Twin 集成模块
 * 
 * 将 Device Twin 模块集成到 Agent 主程序
 */

#include "agent.h"
#include "twin/twin_sync.h"
#include "twin/twin_state.h"
#include "twin/twin_diff.h"
#include <string.h>
#include <pthread.h>

/* Twin 线程 */
static void *twin_thread(void *arg)
{
    agent_context_t *ctx = (agent_context_t *)arg;
    twin_sync_t *sync = (twin_sync_t *)ctx->twin_sync;
    
    LOG_INFO("Twin 线程启动");
    
    while (ctx->running && twin_sync_is_connected(sync)) {
        twin_sync_loop(sync, 1000);
    }
    
    LOG_INFO("Twin 线程退出");
    return NULL;
}

/* Delta 回调 - 处理云端下发的状态变更 */
static void on_delta_changed(twin_sync_t *sync, cJSON *delta)
{
    if (!delta) return;
    
    LOG_INFO("收到 Delta 变更: %s", cJSON_PrintUnformatted(delta));
    
    /* TODO: 根据 delta 执行实际操作
     * 例如：固件更新、配置变更等
     * 执行完成后更新 reported
     */
}

/* 同步完成回调 */
static void on_sync_done(twin_sync_t *sync, bool success)
{
    if (success) {
        LOG_INFO("Twin 同步完成");
    } else {
        LOG_WARN("Twin 同步失败");
    }
}

/* 初始化 Device Twin */
int agent_twin_init(agent_context_t *ctx)
{
    if (!ctx || !ctx->config.enable_twin) {
        return 0;
    }
    
    /* 创建 Twin 状态 */
    twin_state_t *state = calloc(1, sizeof(twin_state_t));
    if (!state) {
        LOG_ERROR("创建 Twin 状态失败");
        return -1;
    }
    
    if (twin_state_init(state, ctx->config.device_id) != 0) {
        LOG_ERROR("初始化 Twin 状态失败");
        free(state);
        return -1;
    }
    ctx->twin_state = state;
    
    /* 配置同步模块 */
    twin_sync_config_t config;
    twin_sync_get_default_config(&config, ctx->config.device_id);
    
    strncpy(config.mqtt_broker, ctx->config.mqtt_broker, sizeof(config.mqtt_broker) - 1);
    config.mqtt_port = ctx->config.mqtt_port;
    strncpy(config.mqtt_username, ctx->config.mqtt_username, sizeof(config.mqtt_username) - 1);
    strncpy(config.mqtt_password, ctx->config.mqtt_password, sizeof(config.mqtt_password) - 1);
    
    /* 创建同步上下文 */
    twin_sync_t *sync = twin_sync_create(state, &config);
    if (!sync) {
        LOG_ERROR("创建 Twin 同步失败");
        twin_state_destroy(state);
        free(state);
        ctx->twin_state = NULL;
        return -1;
    }
    ctx->twin_sync = sync;
    
    /* 设置回调 */
    twin_sync_set_delta_callback(sync, on_delta_changed);
    twin_sync_set_sync_done_callback(sync, on_sync_done);
    
    /* 连接 MQTT */
    if (twin_sync_connect(sync) != 0) {
        LOG_ERROR("连接 MQTT Broker 失败");
        twin_sync_destroy(sync);
        twin_state_destroy(state);
        free(state);
        ctx->twin_sync = NULL;
        ctx->twin_state = NULL;
        return -1;
    }
    
    LOG_INFO("Twin 模块初始化成功");
    return 0;
}

/* 启动 Twin 线程 */
int agent_twin_start(agent_context_t *ctx)
{
    if (!ctx || !ctx->twin_sync) {
        return 0;
    }
    
    pthread_t thread;
    if (pthread_create(&thread, NULL, twin_thread, ctx) != 0) {
        LOG_ERROR("创建 Twin 线程失败");
        return -1;
    }
    pthread_detach(thread);
    
    /* 执行全量同步 */
    twin_sync_full((twin_sync_t *)ctx->twin_sync);
    
    return 0;
}

/* 停止 Twin 模块 */
void agent_twin_stop(agent_context_t *ctx)
{
    if (!ctx) return;
    
    if (ctx->twin_sync) {
        twin_sync_disconnect((twin_sync_t *)ctx->twin_sync);
    }
}

/* 清理 Twin 模块 */
void agent_twin_cleanup(agent_context_t *ctx)
{
    if (!ctx) return;
    
    if (ctx->twin_sync) {
        twin_sync_destroy((twin_sync_t *)ctx->twin_sync);
        ctx->twin_sync = NULL;
    }
    
    if (ctx->twin_state) {
        twin_state_destroy((twin_state_t *)ctx->twin_state);
        free(ctx->twin_state);
        ctx->twin_state = NULL;
    }
    
    LOG_INFO("Twin 模块已清理");
}

/* 上报状态到 Twin */
int agent_twin_report_status(agent_context_t *ctx, const system_status_t *status)
{
    if (!ctx || !ctx->twin_state || !status) {
        return -1;
    }
    
    twin_state_t *state = (twin_state_t *)ctx->twin_state;
    
    /* 构建 reported JSON */
    cJSON *reported = cJSON_CreateObject();
    cJSON *system = cJSON_CreateObject();
    
    cJSON_AddNumberToObject(system, "cpu_usage", status->cpu_usage);
    cJSON_AddNumberToObject(system, "mem_used", status->mem_used);
    cJSON_AddNumberToObject(system, "mem_total", status->mem_total);
    cJSON_AddNumberToObject(system, "disk_used", status->disk_used);
    cJSON_AddNumberToObject(system, "disk_total", status->disk_total);
    cJSON_AddNumberToObject(system, "uptime", status->uptime);
    cJSON_AddStringToObject(system, "hostname", status->hostname);
    cJSON_AddStringToObject(system, "ip", status->ip_addr);
    
    cJSON_AddItemToObject(reported, "system", system);
    
    /* 更新 reported 状态 */
    twin_state_update_reported(state, reported);
    
    /* 同步到云端 */
    if (ctx->twin_sync) {
        twin_sync_report((twin_sync_t *)ctx->twin_sync);
    }
    
    cJSON_Delete(reported);
    return 0;
}