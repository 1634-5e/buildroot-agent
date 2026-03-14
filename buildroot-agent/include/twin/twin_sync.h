/**
 * @file twin_sync.h
 * @brief Device Twin 同步模块
 * 
 * 负责 Twin 状态的 MQTT 同步
 */

#ifndef TWIN_SYNC_H
#define TWIN_SYNC_H

#include "twin/twin_state.h"
#include "twin/mqtt_client.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ==================== 类型定义 ==================== */

/** 同步状态 */
typedef enum {
    TWIN_SYNC_IDLE = 0,          /**< 空闲 */
    TWIN_SYNC_PENDING,           /**< 有待同步数据 */
    TWIN_SYNC_IN_PROGRESS,       /**< 同步中 */
    TWIN_SYNC_ERROR              /**< 同步错误 */
} twin_sync_status_t;

/** 同步配置 */
typedef struct {
    char device_id[64];          /**< 设备 ID */
    
    /* MQTT 配置 */
    char mqtt_broker[256];       /**< Broker 地址 */
    uint16_t mqtt_port;          /**< Broker 端口 */
    char mqtt_username[128];     /**< 用户名 */
    char mqtt_password[128];     /**< 密码 */
    
    /* Topic 模板 */
    char topic_desired[128];     /**< 期望状态 Topic */
    char topic_reported[128];    /**< 已报告状态 Topic */
    char topic_cmd[128];         /**< 命令 Topic */
    
    /* 同步配置 */
    uint32_t sync_interval;      /**< 同步间隔 (毫秒) */
    uint32_t report_interval;    /**< 上报间隔 (毫秒) */
    bool auto_report;            /**< 自动上报系统状态 */
    
} twin_sync_config_t;

/** 同步上下文 */
typedef struct twin_sync twin_sync_t;

/** Delta 变化回调 */
typedef void (*twin_delta_callback_t)(twin_sync_t* sync, cJSON* delta);

/** 同步完成回调 */
typedef void (*twin_sync_done_callback_t)(twin_sync_t* sync, bool success);

/* ==================== 初始化/销毁 ==================== */

/**
 * @brief 创建同步上下文
 * 
 * @param state Twin 状态指针
 * @param config 配置
 * @return 同步上下文指针, NULL 表示失败
 */
twin_sync_t* twin_sync_create(twin_state_t* state, const twin_sync_config_t* config);

/**
 * @brief 销毁同步上下文
 * 
 * @param sync 同步上下文指针
 */
void twin_sync_destroy(twin_sync_t* sync);

/* ==================== 连接管理 ==================== */

/**
 * @brief 连接到 Broker
 * 
 * @param sync 同步上下文指针
 * @return 0 成功, -1 失败
 */
int twin_sync_connect(twin_sync_t* sync);

/**
 * @brief 断开连接
 * 
 * @param sync 同步上下文指针
 * @return 0 成功, -1 失败
 */
int twin_sync_disconnect(twin_sync_t* sync);

/**
 * @brief 检查是否已连接
 * 
 * @param sync 同步上下文指针
 * @return true 已连接, false 未连接
 */
bool twin_sync_is_connected(twin_sync_t* sync);

/* ==================== 同步操作 ==================== */

/**
 * @brief 执行全量同步
 * 
 * 1. 上报当前 reported
 * 2. 请求完整 desired
 * 
 * @param sync 同步上下文指针
 * @return 0 成功, -1 失败
 */
int twin_sync_full(twin_sync_t* sync);

/**
 * @brief 上报当前状态
 * 
 * @param sync 同步上下文指针
 * @return 0 成功, -1 失败
 */
int twin_sync_report(twin_sync_t* sync);

/**
 * @brief 请求完整 desired
 * 
 * @param sync 同步上下文指针
 * @return 0 成功, -1 失败
 */
int twin_sync_request_desired(twin_sync_t* sync);

/* ==================== 事件循环 ==================== */

/**
 * @brief 处理事件 (非阻塞)
 * 
 * @param sync 同步上下文指针
 * @param timeout_ms 超时时间 (毫秒)
 * @return 0 成功, -1 失败
 */
int twin_sync_loop(twin_sync_t* sync, uint32_t timeout_ms);

/* ==================== 回调设置 ==================== */

/**
 * @brief 设置 Delta 变化回调
 * 
 * @param sync 同步上下文指针
 * @param callback 回调函数
 */
void twin_sync_set_delta_callback(twin_sync_t* sync, twin_delta_callback_t callback);

/**
 * @brief 设置同步完成回调
 * 
 * @param sync 同步上下文指针
 * @param callback 回调函数
 */
void twin_sync_set_sync_done_callback(twin_sync_t* sync, twin_sync_done_callback_t callback);

/* ==================== 工具函数 ==================== */

/**
 * @brief 获取默认配置
 * 
 * @param config 配置指针
 * @param device_id 设备 ID
 */
void twin_sync_get_default_config(twin_sync_config_t* config, const char* device_id);

/**
 * @brief 获取同步状态
 * 
 * @param sync 同步上下文指针
 * @return 同步状态
 */
twin_sync_status_t twin_sync_get_status(twin_sync_t* sync);

#ifdef __cplusplus
}
#endif

#endif /* TWIN_SYNC_H */