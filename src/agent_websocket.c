/*
 * WebSocket客户端通信模块
 * 使用libwebsockets库实现WebSocket客户端
 * 特点：仅作为客户端主动连接服务器，不暴露端口
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <libwebsockets.h>
#include "agent.h"
#include <time.h>

/* 兼容不同版本的 libwebsockets: older versions used lws_context_create, newer use lws_create_context */
#if defined(LWS_LIBRARY_VERSION_MAJOR) && (LWS_LIBRARY_VERSION_MAJOR >= 3)
#define LWS_CREATE_CONTEXT lws_create_context
#else
#define LWS_CREATE_CONTEXT lws_context_create
#endif

/* WebSocket客户端结构 */
typedef struct {
    struct lws_context *context;
    struct lws *wsi;
    pthread_t service_thread;
    bool thread_running;
    
    /* 发送缓冲区 */
    unsigned char *send_buffer;
    size_t send_len;
    pthread_mutex_t send_lock;
    pthread_cond_t send_cond;
    bool has_pending_send;
    /* 简单的发送队列，避免单缓冲覆盖/丢弃 */
    struct msg_node *msg_head;
    struct msg_node *msg_tail;
    int queued_count;
    
    /* 接收缓冲区 */
    unsigned char *recv_buffer;
    size_t recv_len;
    size_t recv_capacity;
    
    /* 连接状态 */
    bool connected;
    bool connecting;
    int retry_count;
    
    agent_context_t *agent_ctx;
} ws_client_t;

/* 消息节点 */
struct msg_node {
    unsigned char *data; /* 指向分配的缓冲区，包含 LWS_PRE 前缀 */
    size_t len;          /* 数据长度（不包含 LWS_PRE） */
    struct msg_node *next;
};

static ws_client_t *g_ws_client = NULL;

/* WebSocket回调函数 */
static int ws_callback(struct lws *wsi, enum lws_callback_reasons reason,
                       void *user, void *in, size_t len)
{
    ws_client_t *client = g_ws_client;
    
    if (!client) return 0;
    
    LOG_DEBUG("ws_callback: reason=%d, wsi=%p, len=%zu", reason, wsi, len);
    
    switch (reason) {
    case LWS_CALLBACK_CLIENT_ESTABLISHED:
        LOG_INFO("WebSocket连接已建立");
        client->connected = true;
        client->connecting = false;
        client->retry_count = 0;
        
        if (client->agent_ctx) {
            client->agent_ctx->connected = true;
            /* 发送认证消息，使用统一的入队发送接口 */
            char *auth_msg = protocol_create_auth_msg(client->agent_ctx);
            if (auth_msg) {
                LOG_DEBUG("发送认证消息: %s", auth_msg);
                int rc = ws_send_json(client->agent_ctx, MSG_TYPE_AUTH, auth_msg);
                if (rc != 0) {
                    LOG_ERROR("入队认证消息失败: %d", rc);
                } else {
                    LOG_DEBUG("认证消息已入队 via ws_send_json");
                }
                free(auth_msg);
            } else {
                LOG_ERROR("创建认证消息失败");
            }
        }
        break;
        
    case LWS_CALLBACK_CLIENT_RECEIVE:
        LOG_INFO("收到数据: %zu bytes", len);

        /* 处理接收到的消息 */
        if (client->agent_ctx && in && len > 0) {
            protocol_handle_message(client->agent_ctx, (const char *)in, len);
        }
        break;
        
    case LWS_CALLBACK_CLIENT_WRITEABLE:
        pthread_mutex_lock(&client->send_lock);

        if (client->msg_head) {
            struct msg_node *node = client->msg_head;
            struct timespec _ts_write;
            clock_gettime(CLOCK_REALTIME, &_ts_write);
            LOG_INFO("WRITEABLE: sending queued message, queued=%d, len=%zu, ts=%ld.%09ld", client->queued_count, node->len, (long)_ts_write.tv_sec, _ts_write.tv_nsec);

            int written = lws_write(wsi, node->data + LWS_PRE, node->len, LWS_WRITE_BINARY);
            if (written < 0) {
                LOG_ERROR("WebSocket发送失败: %d", written);
            } else if (written != (int)node->len) {
                LOG_WARN("WebSocket发送不完整: %d/%zu bytes", written, node->len);
            }

            /* 弹出并释放节点 */
            client->msg_head = node->next;
            if (!client->msg_head) client->msg_tail = NULL;
            client->queued_count--;
            free(node->data);
            free(node);

            client->has_pending_send = (client->msg_head != NULL);
            if (client->has_pending_send && client->wsi) {
                lws_callback_on_writable(client->wsi);
            }
            pthread_cond_signal(&client->send_cond);
        } else {
            client->has_pending_send = false;
            pthread_cond_signal(&client->send_cond);
        }
        pthread_mutex_unlock(&client->send_lock);
        break;
        
    default:
        break;
    }
    
    return 0;
}

/* WebSocket协议定义 */
static struct lws_protocols protocols[] = {
    {
        "agent-protocol",
        ws_callback,
        0,
        65536,  /* 接收缓冲区大小 */
    },
    { NULL, NULL, 0, 0 }
};

/* WebSocket服务线程 */
static void *ws_service_thread(void *arg)
{
    ws_client_t *client = (ws_client_t *)arg;
    
    LOG_INFO("WebSocket服务线程启动");
    
    while (client->thread_running) {
        if (client->context) {
            /* 高频处理WebSocket事件以避免任何延迟 */
            lws_service(client->context, 1);
        }
        
        /* 检查是否需要重连 */
        if (!client->connected && !client->connecting && 
            client->agent_ctx && client->agent_ctx->running) {
            /* 在需要重连时进行较短的延迟，以便快速重连 */
            int reconnect_interval = client->agent_ctx->config.reconnect_interval;
            for (int i = 0; i < reconnect_interval && client->thread_running; i++) {
                sleep(1);
            }
            if (client->agent_ctx->running) {
                LOG_INFO("尝试重新连接...");
                ws_connect(client->agent_ctx);
            }
        }
    }
    
    LOG_INFO("WebSocket服务线程退出");
    return NULL;
}

/* 初始化WebSocket客户端 */
static ws_client_t *ws_client_init(agent_context_t *ctx)
{
    ws_client_t *client = calloc(1, sizeof(ws_client_t));
    if (!client) {
        LOG_ERROR("内存分配失败");
        return NULL;
    }
    
    client->agent_ctx = ctx;
    pthread_mutex_init(&client->send_lock, NULL);
    pthread_cond_init(&client->send_cond, NULL);
    
    /* 分配发送缓冲区 */
    client->send_buffer = malloc(LWS_PRE + 65536);
    if (!client->send_buffer) {
        free(client);
        return NULL;
    }
    
    /* 分配接收缓冲区 */
    client->recv_capacity = 65536;
    client->recv_buffer = malloc(client->recv_capacity);
    if (!client->recv_buffer) {
        free(client->send_buffer);
        free(client);
        return NULL;
    }
    
    return client;
}

/* 释放WebSocket客户端 */
static void ws_client_destroy(ws_client_t *client)
{
    if (!client) return;
    
    client->thread_running = false;
    
    if (client->service_thread) {
        pthread_join(client->service_thread, NULL);
    }
    
    if (client->context) {
        lws_context_destroy(client->context);
    }
    
    pthread_mutex_destroy(&client->send_lock);
    pthread_cond_destroy(&client->send_cond);
    
    free(client->send_buffer);
    free(client->recv_buffer);
    free(client);
}

/* 连接到服务器 */
int ws_connect(agent_context_t *ctx)
{
    if (!ctx) return -1;
    
    /* 首次连接，初始化客户端 */
    if (!g_ws_client) {
        g_ws_client = ws_client_init(ctx);
        if (!g_ws_client) {
            return -1;
        }
        ctx->ws_client = g_ws_client;
    }
    
    ws_client_t *client = g_ws_client;
    
    if (client->connected || client->connecting) {
        LOG_WARN("已经连接或正在连接中");
        return 0;
    }
    
    /* 解析URL */
    const char *url = ctx->config.server_url;
    char host[256] = {0};
    char path[256] = "/";
    int port = 443;
    bool use_ssl = true;
    
    if (strncmp(url, "wss://", 6) == 0) {
        url += 6;
        use_ssl = true;
        port = 443;
    } else if (strncmp(url, "ws://", 5) == 0) {
        url += 5;
        use_ssl = false;
        port = 80;
    }
    
    /* 解析host:port/path */
    char *port_ptr = strchr(url, ':');
    char *path_ptr = strchr(url, '/');
    
    if (port_ptr && (!path_ptr || port_ptr < path_ptr)) {
        strncpy(host, url, port_ptr - url);
        port = atoi(port_ptr + 1);
    } else if (path_ptr) {
        strncpy(host, url, path_ptr - url);
    } else {
        strncpy(host, url, sizeof(host) - 1);
    }
    
    if (path_ptr) {
        strncpy(path, path_ptr, sizeof(path) - 1);
    }
    
    LOG_INFO("连接到 %s:%d%s (SSL: %d)", host, port, path, use_ssl);
    
    /* 创建lws上下文 */
    struct lws_context_creation_info ctx_info;
    memset(&ctx_info, 0, sizeof(ctx_info));
    
    ctx_info.port = CONTEXT_PORT_NO_LISTEN;  /* 不监听端口 - 仅作为客户端 */
    ctx_info.protocols = protocols;
    ctx_info.gid = -1;
    ctx_info.uid = -1;
    
    if (use_ssl) {
        ctx_info.options |= LWS_SERVER_OPTION_DO_SSL_GLOBAL_INIT;
    }
    
    /* 销毁旧的context */
    if (client->context) {
        lws_context_destroy(client->context);
    }
    
    client->context = LWS_CREATE_CONTEXT(&ctx_info);
    if (!client->context) {
        LOG_ERROR("创建WebSocket上下文失败");
        return -1;
    }
    
    /* 连接到服务器 */
    struct lws_client_connect_info conn_info;
    memset(&conn_info, 0, sizeof(conn_info));
    
    conn_info.context = client->context;
    conn_info.address = host;
    conn_info.port = port;
    conn_info.path = path;
    conn_info.host = host;
    conn_info.origin = host;
    conn_info.protocol = protocols[0].name;
    
    if (use_ssl) {
        conn_info.ssl_connection = LCCSCF_USE_SSL | 
                                   LCCSCF_ALLOW_SELFSIGNED |
                                   LCCSCF_SKIP_SERVER_CERT_HOSTNAME_CHECK;
    }
    
    client->connecting = true;
    client->wsi = lws_client_connect_via_info(&conn_info);
    
    if (!client->wsi) {
        LOG_ERROR("WebSocket连接失败");
        client->connecting = false;
        return -1;
    }
    
    /* 启动服务线程 */
    if (!client->thread_running) {
        client->thread_running = true;
        if (pthread_create(&client->service_thread, NULL, 
                          ws_service_thread, client) != 0) {
            LOG_ERROR("创建服务线程失败");
            client->thread_running = false;
            return -1;
        }
    }
    
    return 0;
}

/* 断开连接 */
void ws_disconnect(agent_context_t *ctx)
{
    if (!g_ws_client) return;
    
    ws_client_t *client = g_ws_client;
    
    client->thread_running = false;
    client->connected = false;
    
    if (client->wsi) {
        lws_set_timeout(client->wsi, PENDING_TIMEOUT_CLOSE_SEND, 1);
    }
    
    if (ctx) {
        ctx->connected = false;
        ctx->authenticated = false;
    }
    
    LOG_INFO("WebSocket连接已断开");
}

/* 发送消息 */
int ws_send_message(agent_context_t *ctx, msg_type_t type, const char *data, size_t len)
{
    if (!g_ws_client) {
        LOG_WARN("WebSocket客户端未初始化");
        return -1;
    }
    
    ws_client_t *client = g_ws_client;
    
    /* 检查连接状态 */
    if (!client->connected) {
        LOG_WARN("WebSocket未连接，跳过发送");
        return -1;
    }
    
    /* 检查wsi有效性 */
    if (!client->wsi) {
        LOG_WARN("WebSocket连接无效，跳过发送");
        return -1;
    }
    
    pthread_mutex_lock(&client->send_lock);

    if (len > 65535 - 1) {
        pthread_mutex_unlock(&client->send_lock);
        LOG_ERROR("消息太大: %zu > 65534", len);
        return -1;
    }

    size_t buf_len = LWS_PRE + 1 + len;
    unsigned char *buf = malloc(buf_len);
    if (!buf) {
        pthread_mutex_unlock(&client->send_lock);
        LOG_ERROR("内存分配失败: send buffer");
        return -1;
    }
    buf[LWS_PRE] = (unsigned char)type;
    if (data && len > 0) memcpy(buf + LWS_PRE + 1, data, len);

    struct msg_node *node = malloc(sizeof(*node));
    if (!node) {
        free(buf);
        pthread_mutex_unlock(&client->send_lock);
        LOG_ERROR("内存分配失败: msg_node");
        return -1;
    }
    node->data = buf;
    node->len = 1 + len;
    node->next = NULL;

    if (client->msg_tail) client->msg_tail->next = node;
    client->msg_tail = node;
    if (!client->msg_head) client->msg_head = node;
    client->queued_count++;
    client->has_pending_send = true;

    struct timespec _ts_enqueue;
    clock_gettime(CLOCK_REALTIME, &_ts_enqueue);
    LOG_INFO("消息已入队 timestamp=%ld.%09ld: type=0x%02X, len=%zu, queued=%d", (long)_ts_enqueue.tv_sec, _ts_enqueue.tv_nsec, type, node->len, client->queued_count);

    pthread_mutex_unlock(&client->send_lock);

    if (client->wsi) lws_callback_on_writable(client->wsi);

    return 0;
}

/* 发送JSON消息 */
int ws_send_json(agent_context_t *ctx, msg_type_t type, const char *json)
{
    if (!json) return -1;
    return ws_send_message(ctx, type, json, strlen(json));
}

/* 清理WebSocket模块 */
void ws_cleanup(void)
{
    if (g_ws_client) {
        ws_client_destroy(g_ws_client);
        g_ws_client = NULL;
    }
}
