/**
 * @file twin_state.h
 * @brief Device Twin 状态管理模块
 * 
 * 实现设备孪生状态管理，包括：
 * - 期望状态 (desired) 管理
 * - 已报告状态 (reported) 管理
 * - 差异 (delta) 计算
 * - 版本控制
 */

#ifndef TWIN_STATE_H
#define TWIN_STATE_H

#include <stdint.h>
#include <stdbool.h>
#include <time.h>
#include <cjson/cJSON.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ==================== 类型定义 ==================== */

/** 版本号类型 */
typedef uint64_t twin_version_t;

/** 时间戳类型 (Unix timestamp in milliseconds) */
typedef uint64_t twin_timestamp_t;

/** 
 * @brief Twin 状态结构
 * 
 * 核心数据结构，管理设备的期望状态、已报告状态和差异
 */
typedef struct twin_state {
    /* 设备标识 */
    char device_id[64];
    
    /* 期望状态 (云端定义) */
    cJSON* desired;                    /**< 期望状态 JSON 对象 */
    twin_version_t desired_version;    /**< 期望状态版本号 */
    twin_timestamp_t desired_time;     /**< 期望状态更新时间 */
    
    /* 已报告状态 (设备上报) */
    cJSON* reported;                   /**< 已报告状态 JSON 对象 */
    twin_version_t reported_version;   /**< 已报告状态版本号 */
    twin_timestamp_t reported_time;    /**< 已报告状态更新时间 */
    
    /* 差异 (自动计算) */
    cJSON* delta;                      /**< desired 与 reported 的差异 */
    
    /* 同步状态 */
    bool sync_in_progress;             /**< 是否正在同步 */
    bool pending_changes;              /**< 是否有待同步的变更 */
    
    /* 回调函数 */
    void (*on_delta_changed)(struct twin_state* state, cJSON* delta);
    void (*on_desired_received)(struct twin_state* state, cJSON* desired);
    
    /* 内部状态 */
    bool initialized;                  /**< 是否已初始化 */
    char* persist_path;                /**< 持久化文件路径 */
    
} twin_state_t;

/* ==================== 初始化/销毁 ==================== */

/**
 * @brief 初始化 Twin 状态
 * 
 * @param state Twin 状态指针
 * @param device_id 设备 ID
 * @return 0 成功, -1 失败
 */
int twin_state_init(twin_state_t* state, const char* device_id);

/**
 * @brief 销毁 Twin 状态
 * 
 * @param state Twin 状态指针
 */
void twin_state_destroy(twin_state_t* state);

/* ==================== 状态操作 ==================== */

/**
 * @brief 设置期望状态
 * 
 * 版本号必须大于当前版本才会更新
 * 
 * @param state Twin 状态指针
 * @param desired 期望状态 JSON 对象 (会被复制)
 * @param version 版本号
 * @return 0 成功, -1 失败, 1 忽略(版本过旧)
 */
int twin_state_set_desired(twin_state_t* state, cJSON* desired, twin_version_t version);

/**
 * @brief 更新已报告状态 (部分更新)
 * 
 * 合并到现有 reported 中，版本号自动递增
 * 
 * @param state Twin 状态指针
 * @param partial 部分状态 JSON 对象
 * @return 0 成功, -1 失败
 */
int twin_state_update_reported(twin_state_t* state, cJSON* partial);

/**
 * @brief 设置已报告状态 (完整替换)
 * 
 * @param state Twin 状态指针
 * @param reported 完整状态 JSON 对象
 * @param version 版本号
 * @return 0 成功, -1 失败
 */
int twin_state_set_reported(twin_state_t* state, cJSON* reported, twin_version_t version);

/**
 * @brief 重新计算差异
 * 
 * @param state Twin 状态指针
 * @return 0 成功, -1 失败
 */
int twin_state_recalculate_delta(twin_state_t* state);

/* ==================== 状态查询 ==================== */

/**
 * @brief 获取差异
 * 
 * @param state Twin 状态指针
 * @return 差异 JSON 对象 (不要释放，内部引用)
 */
cJSON* twin_state_get_delta(const twin_state_t* state);

/**
 * @brief 检查是否有待处理的变更
 * 
 * @param state Twin 状态指针
 * @return true 有变更, false 无变更
 */
bool twin_state_has_pending_changes(const twin_state_t* state);

/**
 * @brief 检查是否已同步
 * 
 * @param state Twin 状态指针
 * @return true 已同步 (delta 为空), false 未同步
 */
bool twin_state_is_synced(const twin_state_t* state);

/**
 * @brief 获取期望状态的指定字段
 * 
 * @param state Twin 状态指针
 * @param path 字段路径 (如 "config.sampleRate")
 * @return 字段值 JSON 对象 (不要释放，内部引用), NULL 表示不存在
 */
cJSON* twin_state_get_desired_field(const twin_state_t* state, const char* path);

/**
 * @brief 获取已报告状态的指定字段
 * 
 * @param state Twin 状态指针
 * @param path 字段路径 (如 "system.cpuUsage")
 * @return 字段值 JSON 对象 (不要释放，内部引用), NULL 表示不存在
 */
cJSON* twin_state_get_reported_field(const twin_state_t* state, const char* path);

/* ==================== 持久化 ==================== */

/**
 * @brief 从文件加载状态
 * 
 * @param state Twin 状态指针
 * @param filepath 文件路径
 * @return 0 成功, -1 失败, 1 文件不存在
 */
int twin_state_load(twin_state_t* state, const char* filepath);

/**
 * @brief 保存状态到文件
 * 
 * @param state Twin 状态指针
 * @param filepath 文件路径 (NULL 使用 persist_path)
 * @return 0 成功, -1 失败
 */
int twin_state_save(const twin_state_t* state, const char* filepath);

/* ==================== 工具函数 ==================== */

/**
 * @brief 获取当前时间戳 (毫秒)
 * 
 * @return Unix timestamp in milliseconds
 */
twin_timestamp_t twin_state_get_timestamp(void);

/**
 * @brief 打印状态信息 (调试用)
 * 
 * @param state Twin 状态指针
 */
void twin_state_print(const twin_state_t* state);

#ifdef __cplusplus
}
#endif

#endif /* TWIN_STATE_H */