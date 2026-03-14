/**
 * @file mqtt_client.c
 * @brief MQTT 客户端封装实现
 * 
 * 使用 Paho MQTT C 库
 */

#include "twin/mqtt_client.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

/* Paho MQTT C 库 */
#include <MQTTClient.h>

/* ==================== 内部结构 ==================== */

struct mqtt_client {
    mqtt_config_t config;
    MQTTClient client;
    mqtt_state_t state;
    
    /* 回调 */
    mqtt_message_callback_t msg_callback;
    void* msg_user_data;
    
    mqtt_state_callback_t state_callback;
    void* state_user_data;
    
    /* 线程安全 */
    pthread_mutex_t mutex;
    
    /* 重连 */
    int reconnect_attempts;
    bool should_reconnect;
};

/* ==================== 内部常量 ==================== */

#define DEFAULT_KEEPALIVE       60
#define DEFAULT_RECONNECT_MS    5000
#define MAX_RECONNECT_ATTEMPTS  10

/* ==================== 内部函数声明 ==================== */

static void on_connection_lost(void *context, char *cause);
static int on_message_arrived(void *context, char *topicName, int topicLen, MQTTClient_message *message);
static void on_delivery_complete(void *context, MQTTClient_deliveryToken dt);

/* ==================== 公开函数实现 ==================== */

void mqtt_client_get_default_config(mqtt_config_t* config) {
    if (!config) return;
    
    memset(config, 0, sizeof(mqtt_config_t));
    
    strcpy(config->broker_url, "tcp://localhost:1883");
    config->keepalive = DEFAULT_KEEPALIVE;
    config->clean_session = true;
    config->auto_reconnect = true;
    config->reconnect_interval = DEFAULT_RECONNECT_MS;
    config->max_reconnect_attempts = MAX_RECONNECT_ATTEMPTS;
}

mqtt_client_t* mqtt_client_create(const mqtt_config_t* config) {
    if (!config) return NULL;
    
    mqtt_client_t* client = (mqtt_client_t*)calloc(1, sizeof(mqtt_client_t));
    if (!client) return NULL;
    
    /* 复制配置 */
    memcpy(&client->config, config, sizeof(mqtt_config_t));
    client->state = MQTT_STATE_DISCONNECTED;
    
    /* 初始化互斥锁 */
    pthread_mutex_init(&client->mutex, NULL);
    
    /* 创建 Paho 客户端 */
    int rc = MQTTClient_create(
        &client->client,
        config->broker_url,
        config->client_id,
        MQTTCLIENT_PERSISTENCE_NONE,
        NULL
    );
    
    if (rc != MQTTCLIENT_SUCCESS) {
        free(client);
        return NULL;
    }
    
    /* 设置回调 */
    MQTTClient_setCallbacks(
        client->client,
        client,
        on_connection_lost,
        on_message_arrived,
        on_delivery_complete
    );
    
    return client;
}

void mqtt_client_destroy(mqtt_client_t* client) {
    if (!client) return;
    
    if (client->state == MQTT_STATE_CONNECTED) {
        mqtt_client_disconnect(client);
    }
    
    MQTTClient_destroy(&client->client);
    pthread_mutex_destroy(&client->mutex);
    free(client);
}

int mqtt_client_connect(mqtt_client_t* client) {
    if (!client) return -1;
    
    pthread_mutex_lock(&client->mutex);
    
    if (client->state == MQTT_STATE_CONNECTED) {
        pthread_mutex_unlock(&client->mutex);
        return 0;
    }
    
    client->state = MQTT_STATE_CONNECTING;
    pthread_mutex_unlock(&client->mutex);
    
    /* 构建连接选项 */
    MQTTClient_connectOptions opts = MQTTClient_connectOptions_initializer;
    opts.keepAliveInterval = client->config.keepalive;
    opts.cleansession = client->config.clean_session;
    
    if (client->config.username[0]) {
        opts.username = client->config.username;
    }
    if (client->config.password[0]) {
        opts.password = client->config.password;
    }
    
    /* 遗嘱消息 */
    MQTTClient_willOptions will_opts = MQTTClient_willOptions_initializer;
    if (client->config.will_topic[0]) {
        will_opts.topicName = client->config.will_topic;
        will_opts.message = client->config.will_payload;
        will_opts.qos = client->config.will_qos;
        will_opts.retained = client->config.will_retain;
        opts.will = &will_opts;
    }
    
    /* TLS */
    MQTTClient_SSLOptions ssl_opts = MQTTClient_SSLOptions_initializer;
    if (client->config.use_tls) {
        ssl_opts.trustStore = client->config.ca_cert_path;
        ssl_opts.keyStore = client->config.client_cert_path;
        ssl_opts.privateKey = client->config.client_key_path;
        opts.ssl = &ssl_opts;
    }
    
    /* 连接 */
    int rc = MQTTClient_connect(client->client, &opts);
    
    pthread_mutex_lock(&client->mutex);
    if (rc == MQTTCLIENT_SUCCESS) {
        client->state = MQTT_STATE_CONNECTED;
        client->reconnect_attempts = 0;
    } else {
        client->state = MQTT_STATE_ERROR;
    }
    pthread_mutex_unlock(&client->mutex);
    
    /* 状态回调 */
    if (client->state_callback) {
        client->state_callback(client, client->state, client->state_user_data);
    }
    
    return rc == MQTTCLIENT_SUCCESS ? 0 : -1;
}

int mqtt_client_disconnect(mqtt_client_t* client) {
    if (!client) return -1;
    
    pthread_mutex_lock(&client->mutex);
    if (client->state != MQTT_STATE_CONNECTED) {
        pthread_mutex_unlock(&client->mutex);
        return 0;
    }
    client->state = MQTT_STATE_DISCONNECTING;
    pthread_mutex_unlock(&client->mutex);
    
    /* 断开连接 */
    MQTTClient_disconnect(client->client, 5000);
    
    pthread_mutex_lock(&client->mutex);
    client->state = MQTT_STATE_DISCONNECTED;
    pthread_mutex_unlock(&client->mutex);
    
    if (client->state_callback) {
        client->state_callback(client, client->state, client->state_user_data);
    }
    
    return 0;
}

mqtt_state_t mqtt_client_get_state(mqtt_client_t* client) {
    if (!client) return MQTT_STATE_DISCONNECTED;
    return client->state;
}

bool mqtt_client_is_connected(mqtt_client_t* client) {
    if (!client) return false;
    return client->state == MQTT_STATE_CONNECTED;
}

int mqtt_client_publish(
    mqtt_client_t* client,
    const char* topic,
    const void* payload,
    size_t payload_len,
    mqtt_qos_t qos,
    bool retain
) {
    if (!client || !topic || !payload) return -1;
    
    if (!mqtt_client_is_connected(client)) {
        return -1;
    }
    
    MQTTClient_message msg = MQTTClient_message_initializer;
    msg.payload = (void*)payload;
    msg.payloadlen = (int)payload_len;
    msg.qos = qos;
    msg.retained = retain;
    
    MQTTClient_deliveryToken token;
    int rc = MQTTClient_publishMessage(client->client, topic, &msg, &token);
    
    if (rc == MQTTCLIENT_SUCCESS) {
        /* 等待确认 (QoS 1/2) */
        if (qos > MQTT_QOS_0) {
            MQTTClient_waitForCompletion(client->client, token, 5000);
        }
        return 0;
    }
    
    return -1;
}

int mqtt_client_subscribe(
    mqtt_client_t* client,
    const char* topic,
    mqtt_qos_t qos
) {
    if (!client || !topic) return -1;
    
    if (!mqtt_client_is_connected(client)) {
        return -1;
    }
    
    int rc = MQTTClient_subscribe(client->client, topic, qos);
    return rc == MQTTCLIENT_SUCCESS ? 0 : -1;
}

int mqtt_client_unsubscribe(
    mqtt_client_t* client,
    const char* topic
) {
    if (!client || !topic) return -1;
    
    if (!mqtt_client_is_connected(client)) {
        return -1;
    }
    
    int rc = MQTTClient_unsubscribe(client->client, topic);
    return rc == MQTTCLIENT_SUCCESS ? 0 : -1;
}

void mqtt_client_set_message_callback(
    mqtt_client_t* client,
    mqtt_message_callback_t callback,
    void* user_data
) {
    if (!client) return;
    client->msg_callback = callback;
    client->msg_user_data = user_data;
}

void mqtt_client_set_state_callback(
    mqtt_client_t* client,
    mqtt_state_callback_t callback,
    void* user_data
) {
    if (!client) return;
    client->state_callback = callback;
    client->state_user_data = user_data;
}

int mqtt_client_loop(mqtt_client_t* client, uint32_t timeout_ms) {
    if (!client) return -1;
    
    /* Paho 使用回调模式，loop 主要用于触发内部处理 */
    /* 在回调模式下，不需要显式调用 yield */
    
    (void)timeout_ms;
    return 0;
}

int mqtt_client_wait(mqtt_client_t* client, int32_t timeout_ms) {
    if (!client) return -1;
    
    /* 简单的等待循环 */
    int elapsed = 0;
    while (timeout_ms < 0 || elapsed < timeout_ms) {
        if (!mqtt_client_is_connected(client)) {
            return -1;
        }
        
        mqtt_client_loop(client, 100);
        elapsed += 100;
    }
    
    return 0;
}

/* ==================== 内部函数实现 ==================== */

static void on_connection_lost(void *context, char *cause) {
    mqtt_client_t* client = (mqtt_client_t*)context;
    
    pthread_mutex_lock(&client->mutex);
    client->state = MQTT_STATE_DISCONNECTED;
    pthread_mutex_unlock(&client->mutex);
    
    if (client->state_callback) {
        client->state_callback(client, MQTT_STATE_DISCONNECTED, client->state_user_data);
    }
    
    (void)cause;  /* 未使用 */
}

static int on_message_arrived(void *context, char *topicName, int topicLen, MQTTClient_message *message) {
    mqtt_client_t* client = (mqtt_client_t*)context;
    
    if (client->msg_callback) {
        client->msg_callback(
            client,
            topicName,
            message->payload,
            message->payloadlen,
            client->msg_user_data
        );
    }
    
    MQTTClient_freeMessage(&message);
    MQTTClient_free(topicName);
    
    return 1;
}

static void on_delivery_complete(void *context, MQTTClient_deliveryToken dt) {
    (void)context;
    (void)dt;
}