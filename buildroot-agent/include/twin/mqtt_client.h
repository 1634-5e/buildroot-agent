/**
 * @file mqtt_client.h
 * @brief MQTT 客户端封装
 * 
 * 封装 Paho MQTT C 库，提供简化的 API
 */

#ifndef MQTT_CLIENT_H
#define MQTT_CLIENT_H

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ==================== 类型定义 ==================== */

/** QoS 级别 */
typedef enum {
    MQTT_QOS_0 = 0,  /**< 最多一次 */
    MQTT_QOS_1 = 1,  /**< 至少一次 */
    MQTT_QOS_2 = 2   /**< 恰好一次 */
} mqtt_qos_t;

/** 连接状态 */
typedef enum {
    MQTT_STATE_DISCONNECTED = 0,
    MQTT_STATE_CONNECTING,
    MQTT_STATE_CONNECTED,
    MQTT_STATE_DISCONNECTING,
    MQTT_STATE_ERROR
} mqtt_state_t;

/** MQTT 客户端配置 */
typedef struct {
    char broker_url[256];        /**< Broker 地址 (如 "tcp://localhost:1883") */
    char client_id[64];          /**< 客户端 ID */
    char username[128];          /**< 用户名 (可选) */
    char password[128];          /**< 密码 (可选) */
    
    uint16_t keepalive;          /**< 心跳间隔 (秒), 默认 60 */
    bool clean_session;          /**< 清除会话, 默认 true */
    
    /* TLS 配置 */
    bool use_tls;                /**< 是否使用 TLS */
    char ca_cert_path[256];      /**< CA 证书路径 */
    char client_cert_path[256];  /**< 客户端证书路径 */
    char client_key_path[256];   /**< 客户端私钥路径 */
    
    /* 遗嘱消息 */
    char will_topic[128];        /**< 遗嘱主题 */
    char will_payload[512];      /**< 遗嘱消息 */
    mqtt_qos_t will_qos;         /**< 遗嘱 QoS */
    bool will_retain;            /**< 遗嘱保留 */
    
    /* 重连配置 */
    bool auto_reconnect;         /**< 自动重连 */
    uint32_t reconnect_interval; /**< 重连间隔 (毫秒), 默认 5000 */
    int max_reconnect_attempts;  /**< 最大重连次数, -1 表示无限 */
    
} mqtt_config_t;

/** MQTT 客户端结构 */
typedef struct mqtt_client mqtt_client_t;

/** 消息回调函数类型 */
typedef void (*mqtt_message_callback_t)(
    mqtt_client_t* client,
    const char* topic,
    const void* payload,
    size_t payload_len,
    void* user_data
);

/** 连接状态回调函数类型 */
typedef void (*mqtt_state_callback_t)(
    mqtt_client_t* client,
    mqtt_state_t state,
    void* user_data
);

/* ==================== 初始化/销毁 ==================== */

/**
 * @brief 创建 MQTT 客户端
 * 
 * @param config 配置
 * @return 客户端指针, NULL 表示失败
 */
mqtt_client_t* mqtt_client_create(const mqtt_config_t* config);

/**
 * @brief 销毁 MQTT 客户端
 * 
 * @param client 客户端指针
 */
void mqtt_client_destroy(mqtt_client_t* client);

/* ==================== 连接管理 ==================== */

/**
 * @brief 连接到 Broker
 * 
 * @param client 客户端指针
 * @return 0 成功, -1 失败
 */
int mqtt_client_connect(mqtt_client_t* client);

/**
 * @brief 断开连接
 * 
 * @param client 客户端指针
 * @return 0 成功, -1 失败
 */
int mqtt_client_disconnect(mqtt_client_t* client);

/**
 * @brief 获取连接状态
 * 
 * @param client 客户端指针
 * @return 连接状态
 */
mqtt_state_t mqtt_client_get_state(mqtt_client_t* client);

/**
 * @brief 检查是否已连接
 * 
 * @param client 客户端指针
 * @return true 已连接, false 未连接
 */
bool mqtt_client_is_connected(mqtt_client_t* client);

/* ==================== 发布/订阅 ==================== */

/**
 * @brief 发布消息
 * 
 * @param client 客户端指针
 * @param topic 主题
 * @param payload 消息体
 * @param payload_len 消息长度
 * @param qos QoS 级别
 * @param retain 是否保留
 * @return 0 成功, -1 失败
 */
int mqtt_client_publish(
    mqtt_client_t* client,
    const char* topic,
    const void* payload,
    size_t payload_len,
    mqtt_qos_t qos,
    bool retain
);

/**
 * @brief 订阅主题
 * 
 * @param client 客户端指针
 * @param topic 主题 (支持通配符)
 * @param qos QoS 级别
 * @return 0 成功, -1 失败
 */
int mqtt_client_subscribe(
    mqtt_client_t* client,
    const char* topic,
    mqtt_qos_t qos
);

/**
 * @brief 取消订阅
 * 
 * @param client 客户端指针
 * @param topic 主题
 * @return 0 成功, -1 失败
 */
int mqtt_client_unsubscribe(
    mqtt_client_t* client,
    const char* topic
);

/* ==================== 回调设置 ==================== */

/**
 * @brief 设置消息回调
 * 
 * @param client 客户端指针
 * @param callback 回调函数
 * @param user_data 用户数据
 */
void mqtt_client_set_message_callback(
    mqtt_client_t* client,
    mqtt_message_callback_t callback,
    void* user_data
);

/**
 * @brief 设置连接状态回调
 * 
 * @param client 客户端指针
 * @param callback 回调函数
 * @param user_data 用户数据
 */
void mqtt_client_set_state_callback(
    mqtt_client_t* client,
    mqtt_state_callback_t callback,
    void* user_data
);

/* ==================== 事件循环 ==================== */

/**
 * @brief 处理事件 (非阻塞)
 * 
 * @param client 客户端指针
 * @param timeout_ms 超时时间 (毫秒), 0 表示立即返回
 * @return 0 成功, -1 失败
 */
int mqtt_client_loop(mqtt_client_t* client, uint32_t timeout_ms);

/**
 * @brief 阻塞等待 (用于简单场景)
 * 
 * @param client 客户端指针
 * @param timeout_ms 超时时间 (毫秒), -1 表示无限等待
 * @return 0 成功, -1 失败
 */
int mqtt_client_wait(mqtt_client_t* client, int32_t timeout_ms);

/* ==================== 工具函数 ==================== */

/**
 * @brief 获取默认配置
 * 
 * @param config 配置指针
 */
void mqtt_client_get_default_config(mqtt_config_t* config);

#ifdef __cplusplus
}
#endif

#endif /* MQTT_CLIENT_H */