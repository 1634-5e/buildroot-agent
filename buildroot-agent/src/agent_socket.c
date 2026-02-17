/*
 * Socket客户端通信模块
 * 使用标准socket实现TCP客户端（移除SSL）
 * 特点：仅作为客户端主动连接服务器，不暴露端口
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <errno.h>
#include <netdb.h>
#include <sys/socket.h>
#include <sys/poll.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include "agent.h"
#include <time.h>

#define CONNECT_TIMEOUT_SEC 30
#define MAX_CONNECT_RETRIES 3
#define POLL_TIMEOUT_MS 1000

/* Socket客户端结构 */
typedef struct {
    int sock_fd;                /* Socket文件描述符 */
    pthread_t recv_thread;      /* 接收线程 */
    bool thread_running;
    
    /* 发送队列 */
    struct msg_node *msg_head;
    struct msg_node *msg_tail;
    int queued_count;
    pthread_mutex_t send_lock;
    pthread_cond_t send_cond;
    pthread_t send_thread;      /* 发送线程句柄 */
    bool send_thread_running;    /* 发送线程运行标志 */
    
    /* 连接状态 */
    bool connected;
    bool connecting;
    int retry_count;
    
    /* 重连机制 */
    bool should_reconnect;            /* 是否启用自动重连 */
    pthread_t reconnect_thread;       /* 重连监控线程 */
    bool reconnect_thread_running;    /* 重连线程运行状态 */
    int current_retry_delay;           /* 当前重连延迟（秒） */
    int base_retry_delay;              /* 基础重连延迟（秒） */
    int max_retry_delay;               /* 最大重连延迟（秒） */
    pthread_mutex_t reconnect_lock;    /* 重连状态互斥锁 */
    pthread_cond_t reconnect_cond;     /* 重连条件变量（用于通知连接断开） */
    bool reconnect_notify;             /* 连接断开通知标志 */

    /* 注册状态 */
    pthread_mutex_t register_lock;     /* 注册状态互斥锁 */
    pthread_cond_t register_cond;      /* 注册条件变量 */
    bool register_completed;           /* 注册完成标志 */

    agent_context_t *agent_ctx;
} socket_client_t;

/* 消息节点 */
struct msg_node {
    unsigned char *data;
    size_t len;
    struct msg_node *next;
};

static socket_client_t *g_socket_client = NULL;
static bool g_client_initialized = false;

/* 函数前向声明 */
static int do_connect(socket_client_t *client, const char *host, int port);

/* 连接超时控制 */
static int connect_with_timeout(int sock_fd, struct sockaddr *addr, socklen_t addr_len, int timeout_sec)
{
    int flags, ret;
    struct pollfd pfd;
    
    flags = fcntl(sock_fd, F_GETFL, 0);
    fcntl(sock_fd, F_SETFL, flags | O_NONBLOCK);
    
    ret = connect(sock_fd, addr, addr_len);
    if (ret < 0 && errno != EINPROGRESS) {
        return -1;
    }
    
    if (ret == 0) {
        fcntl(sock_fd, F_SETFL, flags);
        return 0;
    }
    
    pfd.fd = sock_fd;
    pfd.events = POLLOUT;
    
    ret = poll(&pfd, 1, timeout_sec * 1000);
    if (ret <= 0) {
        return -1;
    }
    
    int so_error;
    socklen_t len = sizeof(so_error);
    getsockopt(sock_fd, SOL_SOCKET, SO_ERROR, &so_error, &len);
    if (so_error != 0) {
        errno = so_error;
        return -1;
    }
    
    fcntl(sock_fd, F_SETFL, flags);
    return 0;
}

/* 接收线程 */
static void *socket_recv_thread(void *arg)
{
    socket_client_t *client = (socket_client_t *)arg;
    unsigned char recv_buf[65536];
    
    LOG_INFO("Socket接收线程启动");
    
    while (1) {
        pthread_mutex_lock(&client->reconnect_lock);
        bool thread_running = client->thread_running;
        bool connected = client->connected;
        pthread_mutex_unlock(&client->reconnect_lock);
        
        if (!thread_running || !connected) {
            break;
        }
        
        /* 使用poll()添加超时，避免无限阻塞，确保能响应Ctrl-C */
        struct pollfd pfd = { .fd = client->sock_fd, .events = POLLIN };
        int poll_ret = poll(&pfd, 1, POLL_TIMEOUT_MS);
        
        if (poll_ret < 0) {
            if (errno == EINTR) {
                continue;
            }
            LOG_ERROR("poll错误: %s", strerror(errno));
            break;
        } else if (poll_ret == 0) {
            continue;  /* 超时，继续检查thread_running标志 */
        }
        
        int bytes_received = recv(client->sock_fd, recv_buf, sizeof(recv_buf), 0);
        
        if (bytes_received <= 0) {
            if (bytes_received == 0) {
                LOG_INFO("服务器关闭连接");
                break;
            } else {
                if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
                    continue;
                }
                LOG_ERROR("接收数据错误: %s", strerror(errno));
                break;
            }
        }
        
        LOG_DEBUG("收到数据: %d bytes", bytes_received);
        
        if (client->agent_ctx && bytes_received > 0) {
            protocol_handle_message(client->agent_ctx, (const char *)recv_buf, bytes_received);
        }
    }
    
    LOG_INFO("Socket接收线程退出");

    pthread_mutex_lock(&g_socket_client->reconnect_lock);
    client->thread_running = false;
    client->connected = false;
    client->reconnect_notify = true;
    pthread_cond_signal(&client->reconnect_cond);
    pthread_mutex_unlock(&g_socket_client->reconnect_lock);

    /* 设置agent的connected状态，停止心跳和状态线程 */
    pthread_mutex_lock(&g_socket_client->agent_ctx->lock);
    g_socket_client->agent_ctx->connected = false;
    pthread_mutex_unlock(&g_socket_client->agent_ctx->lock);

    return NULL;
}

/* 发送线程 */
static void *socket_send_thread(void *arg)
{
    socket_client_t *client = (socket_client_t *)arg;
    
    LOG_INFO("Socket发送线程启动");
    
    while (client->send_thread_running) {
        pthread_mutex_lock(&client->send_lock);
        
        while (client->msg_head == NULL && client->send_thread_running) {
            pthread_cond_wait(&client->send_cond, &client->send_lock);
        }
        
        if (!client->send_thread_running) {
            pthread_mutex_unlock(&client->send_lock);
            break;
        }
        
        struct msg_node *node = client->msg_head;
        client->msg_head = node->next;
        if (client->msg_head == NULL) {
            client->msg_tail = NULL;
        }
        client->queued_count--;
        
        pthread_mutex_unlock(&client->send_lock);
        
        bool connected;
        pthread_mutex_lock(&client->reconnect_lock);
        connected = client->connected;
        pthread_mutex_unlock(&client->reconnect_lock);
        
        if (connected && client->sock_fd >= 0) {
            size_t total_sent = 0;
            while (total_sent < node->len) {
                ssize_t send_ret = send(client->sock_fd, node->data + total_sent, node->len - total_sent, 0);
                
                if (send_ret < 0) {
                    if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
                        usleep(10000);
                        continue;
                    }
                    LOG_ERROR("发送数据错误: %s", strerror(errno));
                    break;
                }
                
                total_sent += send_ret;
            }
        }
        
        free(node->data);
        free(node);
    }
    
    LOG_INFO("Socket发送线程退出");
    return NULL;
}

/* 连接服务器 */
static int do_connect(socket_client_t *client, const char *host, int port)
{
    struct sockaddr_in server_addr;
    struct hostent *he;
    int retry = 0;
    
    client->sock_fd = -1;
    
    /* 内层快速重试：最多2次（初始1次+快速重试1次），间隔1秒 */
    for (retry = 0; retry < 2 && g_agent_ctx && g_agent_ctx->running; retry++) {
        if (!g_agent_ctx || !g_agent_ctx->running) {
            break;  // 退出重试循环
        }
        
        if (retry > 0) {
            LOG_INFO("快速重试连接 (%d/1)...", retry);
            sleep(1);
        }
        
        if (!g_agent_ctx || !g_agent_ctx->running) {
            break;
        }
        
        client->sock_fd = socket(AF_INET, SOCK_STREAM, 0);
        if (client->sock_fd < 0) {
            LOG_ERROR("创建socket失败: %s", strerror(errno));
            return -1;
        }
        
        he = gethostbyname(host);
        if (!he) {
            LOG_ERROR("无法解析主机名: %s", host);
            close(client->sock_fd);
            return -1;
        }
        
        memset(&server_addr, 0, sizeof(server_addr));
        server_addr.sin_family = AF_INET;
        server_addr.sin_port = htons(port);
        memcpy(&server_addr.sin_addr, he->h_addr_list[0], he->h_length);
        
        LOG_INFO("连接到 %s:%d", host, port);
        
        if (connect_with_timeout(client->sock_fd, (struct sockaddr *)&server_addr, sizeof(server_addr), CONNECT_TIMEOUT_SEC) < 0) {
            LOG_ERROR("连接失败: %s", strerror(errno));
            close(client->sock_fd);
            client->sock_fd = -1;
            continue;
        }
        
        LOG_INFO("TCP连接建立成功");
        return 0;
    }
    
    if (client->sock_fd >= 0) {
        close(client->sock_fd);
        client->sock_fd = -1;
    }
    
    return -1;
}

/* 发送注册消息前向声明 */
static int send_register_message(agent_context_t *ctx);

/* 重连服务器（不销毁客户端结构）*/
static int do_reconnect(socket_client_t *client, const char *host, int port)
{
    pthread_mutex_lock(&client->reconnect_lock);
    client->connecting = true;
    pthread_mutex_unlock(&client->reconnect_lock);
    
    /* 清理旧的socket和线程 */
    if (client->send_thread) {
        pthread_mutex_lock(&client->send_lock);
        client->send_thread_running = false;
        pthread_cond_signal(&client->send_cond);
        pthread_mutex_unlock(&client->send_lock);
        pthread_join(client->send_thread, NULL);
    }
    
    if (client->thread_running) {
        client->thread_running = false;
    }
    
    if (client->recv_thread) {
        pthread_join(client->recv_thread, NULL);
    }
    
    if (client->sock_fd >= 0) {
        shutdown(client->sock_fd, SHUT_RDWR);
        close(client->sock_fd);
        client->sock_fd = -1;
    }
    
    /* 清空发送队列 */
    pthread_mutex_lock(&client->send_lock);
    struct msg_node *node = client->msg_head;
    while (node) {
        struct msg_node *next = node->next;
        free(node->data);
        free(node);
        node = next;
    }
    client->msg_head = NULL;
    client->msg_tail = NULL;
    client->queued_count = 0;
    pthread_mutex_unlock(&client->send_lock);
    
    int ret = do_connect(client, host, port);
    
    pthread_mutex_lock(&client->reconnect_lock);
    client->connecting = false;
    if (ret == 0) {
        client->connected = true;
        client->retry_count = 0;
        client->thread_running = true;
    } else {
        client->connected = false;
    }
    pthread_mutex_unlock(&client->reconnect_lock);
    
    if (ret == 0) {
        pthread_create(&client->recv_thread, NULL, socket_recv_thread, client);

        client->send_thread_running = true;
        pthread_create(&client->send_thread, NULL, socket_send_thread, client);

        pthread_mutex_lock(&client->agent_ctx->lock);
        client->agent_ctx->connected = true;
        client->agent_ctx->registered = false;
        pthread_mutex_unlock(&client->agent_ctx->lock);

        /* 重置注册完成标志 */
        pthread_mutex_lock(&client->register_lock);
        client->register_completed = false;
        pthread_mutex_unlock(&client->register_lock);

        LOG_INFO("Agent已连接，设备ID: %s", client->agent_ctx->config.device_id);

        /* 发送注册消息 */
        if (send_register_message(client->agent_ctx) != 0) {
            LOG_ERROR("重连后发送注册消息失败");
            ret = -1;
        } else {
            /* 等待注册结果（5秒超时） */
            struct timespec ts;
            clock_gettime(CLOCK_REALTIME, &ts);
            ts.tv_sec += 5;

            pthread_mutex_lock(&client->register_lock);
            while (!client->register_completed && ret == 0) {
                int wait_ret = pthread_cond_timedwait(&client->register_cond,
                                                       &client->register_lock, &ts);
                if (wait_ret == ETIMEDOUT) {
                    LOG_ERROR("等待注册结果超时");
                    ret = -1;
                    break;
                }
            }
            pthread_mutex_unlock(&client->register_lock);

            if (ret == 0) {
                LOG_INFO("设备重新注册成功");
            }
        }
    }

    return ret;
}

/* 初始化Socket客户端 */
static socket_client_t *socket_client_init(agent_context_t *ctx)
{
    socket_client_t *client = (socket_client_t *)calloc(1, sizeof(socket_client_t));
    if (!client) {
        LOG_ERROR("内存分配失败");
        return NULL;
    }
    
    client->sock_fd = -1;
    client->thread_running = false;
    client->send_thread_running = true;
    client->connected = false;
    client->connecting = false;
    client->retry_count = 0;
    client->should_reconnect = true;
    client->reconnect_thread_running = false;
    client->current_retry_delay = 5;
    client->base_retry_delay = 5;
    client->max_retry_delay = 60;
    client->msg_head = NULL;
    client->msg_tail = NULL;
    client->queued_count = 0;
    client->agent_ctx = ctx;

    pthread_mutex_init(&client->send_lock, NULL);
    pthread_cond_init(&client->send_cond, NULL);
    pthread_mutex_init(&client->reconnect_lock, NULL);
    pthread_cond_init(&client->reconnect_cond, NULL);
    client->reconnect_notify = false;

    pthread_mutex_init(&client->register_lock, NULL);
    pthread_cond_init(&client->register_cond, NULL);
    client->register_completed = false;

    return client;
}

/* 清理Socket客户端 */
static void socket_client_cleanup(socket_client_t *client)
{
    if (!client) {
        return;
    }
    
    pthread_mutex_lock(&client->reconnect_lock);
    client->should_reconnect = false;
    client->thread_running = false;
    client->connected = false;
    pthread_cond_broadcast(&client->reconnect_cond);
    pthread_mutex_unlock(&client->reconnect_lock);

    /* 重置注册状态 */
    pthread_mutex_lock(&client->register_lock);
    client->register_completed = false;
    pthread_cond_broadcast(&client->register_cond);
    pthread_mutex_unlock(&client->register_lock);
    
    /* 停止并等待发送线程退出 */
    pthread_mutex_lock(&client->send_lock);
    client->send_thread_running = false;
    pthread_cond_signal(&client->send_cond);
    pthread_mutex_unlock(&client->send_lock);
    
    if (client->send_thread) {
        pthread_join(client->send_thread, NULL);
    }
    
    if (client->recv_thread) {
        pthread_join(client->recv_thread, NULL);
    }
    
    if (client->sock_fd >= 0) {
        shutdown(client->sock_fd, SHUT_RDWR);
        close(client->sock_fd);
        client->sock_fd = -1;
    }
    
    pthread_mutex_lock(&client->send_lock);
    struct msg_node *node = client->msg_head;
    while (node) {
        struct msg_node *next = node->next;
        free(node->data);
        free(node);
        node = next;
    }
    client->msg_head = NULL;
    client->msg_tail = NULL;
    client->queued_count = 0;
    pthread_mutex_unlock(&client->send_lock);
    
    pthread_mutex_destroy(&client->send_lock);
    pthread_cond_destroy(&client->send_cond);
    pthread_mutex_destroy(&client->reconnect_lock);
    pthread_cond_destroy(&client->reconnect_cond);

    pthread_mutex_destroy(&client->register_lock);
    pthread_cond_destroy(&client->register_cond);
}

/* 解析服务器地址 (host:port) */
static int parse_server_addr(const char *addr, char *host, size_t host_size, int *port)
{
    char *colon = strrchr(addr, ':');
    if (!colon) {
        LOG_ERROR("无效的服务器地址格式: %s", addr);
        return -1;
    }
    
    size_t host_len = colon - addr;
    if (host_len >= host_size) {
        LOG_ERROR("服务器地址过长");
        return -1;
    }
    
    memcpy(host, addr, host_len);
    host[host_len] = '\0';
    *port = atoi(colon + 1);
    
    return 0;
}

/* 连接服务器 */
int socket_connect(agent_context_t *ctx)
{
    if (!ctx) {
        return -1;
    }
    
    char host[256];
    int port;
    
    if (parse_server_addr(ctx->config.server_addr, host, sizeof(host), &port) != 0) {
        return -1;
    }
    
    /* 只在首次连接时创建客户端，后续不销毁 */
    if (!g_socket_client) {
        g_socket_client = socket_client_init(ctx);
        if (!g_socket_client) {
            return -1;
        }
        g_client_initialized = true;
    }
    
    pthread_mutex_lock(&g_socket_client->reconnect_lock);
    g_socket_client->connecting = true;
    pthread_mutex_unlock(&g_socket_client->reconnect_lock);
    
    int ret = do_connect(g_socket_client, host, port);
    
    pthread_mutex_lock(&g_socket_client->reconnect_lock);
    g_socket_client->connecting = false;
    if (ret == 0) {
        g_socket_client->connected = true;
        g_socket_client->retry_count = 0;
    }
    pthread_mutex_unlock(&g_socket_client->reconnect_lock);
    
    if (ret == 0) {
        g_socket_client->thread_running = true;
        pthread_create(&g_socket_client->recv_thread, NULL, socket_recv_thread, g_socket_client);

        /* 启动发送线程 */
        pthread_create(&g_socket_client->send_thread, NULL, socket_send_thread, g_socket_client);

        /* 设置agent的connected状态，使心跳和状态线程能够工作 */
        pthread_mutex_lock(&g_socket_client->agent_ctx->lock);
        g_socket_client->agent_ctx->connected = true;
        g_socket_client->agent_ctx->registered = false;
        pthread_mutex_unlock(&g_socket_client->agent_ctx->lock);

        /* 重置注册完成标志 */
        pthread_mutex_lock(&g_socket_client->register_lock);
        g_socket_client->register_completed = false;
        pthread_mutex_unlock(&g_socket_client->register_lock);

            LOG_INFO("Agent已连接，设备ID: %s", g_socket_client->agent_ctx->config.device_id);

        /* 发送注册消息 */
        if (send_register_message(g_socket_client->agent_ctx) != 0) {
            LOG_ERROR("发送注册消息失败");
            ret = -1;
        } else {
            /* 等待注册结果（5秒超时） */
            struct timespec ts;
            clock_gettime(CLOCK_REALTIME, &ts);
            ts.tv_sec += 5;

            pthread_mutex_lock(&g_socket_client->register_lock);
            while (!g_socket_client->register_completed && ret == 0) {
                int wait_ret = pthread_cond_timedwait(&g_socket_client->register_cond,
                                                       &g_socket_client->register_lock, &ts);
                if (wait_ret == ETIMEDOUT) {
                    LOG_ERROR("等待注册结果超时");
                    ret = -1;
                    break;
                }
            }
            pthread_mutex_unlock(&g_socket_client->register_lock);

            if (ret == 0) {
                LOG_INFO("设备注册成功");
            }
        }
    }

    return ret;
}

/* 发送注册消息 */
static int send_register_message(agent_context_t *ctx)
{
    if (!ctx) {
        return -1;
    }

    char json[512];
    int len = snprintf(json, sizeof(json),
        "{\"device_id\":\"%s\",\"version\":\"%s\"}",
        ctx->config.device_id,
        ctx->config.version);

    if (len < 0 || len >= (int)sizeof(json)) {
        LOG_ERROR("构建注册消息失败");
        return -1;
    }

    LOG_DEBUG("发送注册消息: %s", json);

    if (socket_send_json(ctx, MSG_TYPE_REGISTER, json) != 0) {
        LOG_ERROR("发送注册消息失败");
        return -1;
    }

    LOG_INFO("注册消息已发送，设备ID: %s", ctx->config.device_id);
    return 0;
}

/* 标记注册完成 */
void socket_registration_complete(agent_context_t *ctx, bool success)
{
    if (!ctx || !g_socket_client) {
        return;
    }

    pthread_mutex_lock(&ctx->lock);
    ctx->registered = success;
    pthread_mutex_unlock(&ctx->lock);

    pthread_mutex_lock(&g_socket_client->register_lock);
    g_socket_client->register_completed = true;
    pthread_cond_broadcast(&g_socket_client->register_cond);
    pthread_mutex_unlock(&g_socket_client->register_lock);

    LOG_INFO("注册状态更新: %s", success ? "成功" : "失败");
}

/* 断开连接 */
void socket_disconnect(agent_context_t *ctx)
{
    if (!ctx) {
        return;
    }

    if (!g_socket_client) {
        return;
    }

    /* 设置agent的connected和registered状态，停止心跳和状态线程 */
    pthread_mutex_lock(&ctx->lock);
    ctx->connected = false;
    ctx->registered = false;
    pthread_mutex_unlock(&ctx->lock);

    g_socket_client->should_reconnect = false;

    socket_client_cleanup(g_socket_client);
    free(g_socket_client);
    g_socket_client = NULL;
}

/* 发送消息 */
int socket_send_message(agent_context_t *ctx, msg_type_t type, const char *data, size_t len)
{
    (void)ctx;

    if (!g_socket_client) {
        return -1;
    }

    bool connected;
    pthread_mutex_lock(&g_socket_client->reconnect_lock);
    connected = g_socket_client->connected;
    pthread_mutex_unlock(&g_socket_client->reconnect_lock);

    if (!connected) {
        return -1;
    }

    /* 检查注册状态 - 只有REGISTER消息可以在未注册时发送 */
    if (type != MSG_TYPE_REGISTER) {
        bool registered;
        pthread_mutex_lock(&g_socket_client->agent_ctx->lock);
        registered = g_socket_client->agent_ctx->registered;
        pthread_mutex_unlock(&g_socket_client->agent_ctx->lock);

        if (!registered) {
            LOG_ERROR("消息发送失败: 设备未注册，消息类型=0x%02X", type);
            return -1;
        }
    }

    /* 消息格式: [type(1字节)] + [length(2字节,大端)] + [data] */
    unsigned char *send_buf = (unsigned char *)malloc(len + 3);
    if (!send_buf) {
        return -1;
    }

    send_buf[0] = (unsigned char)type;
    send_buf[1] = (len >> 8) & 0xFF;
    send_buf[2] = len & 0xFF;
    memcpy(send_buf + 3, data, len);

    struct msg_node *node = (struct msg_node *)malloc(sizeof(struct msg_node));
    if (!node) {
        free(send_buf);
        return -1;
    }

    node->data = send_buf;
    node->len = len + 3;
    node->next = NULL;

    pthread_mutex_lock(&g_socket_client->send_lock);
    if (g_socket_client->msg_tail) {
        g_socket_client->msg_tail->next = node;
    } else {
        g_socket_client->msg_head = node;
    }
    g_socket_client->msg_tail = node;
    g_socket_client->queued_count++;
    pthread_cond_signal(&g_socket_client->send_cond);
    pthread_mutex_unlock(&g_socket_client->send_lock);

    return 0;
}

/* 重连监控线程 */
static void *socket_reconnect_thread(void *arg)
{
    socket_client_t *client = (socket_client_t *)arg;
    
    LOG_INFO("重连线程启动");
    
    while (client->should_reconnect && g_agent_ctx && g_agent_ctx->running) {
        pthread_mutex_lock(&client->reconnect_lock);
        client->reconnect_thread_running = true;
        bool connecting = client->connecting;
        bool connected = client->connected;
        int retry_delay = client->current_retry_delay;
        pthread_mutex_unlock(&client->reconnect_lock);
        
        if (connected) {
            /* 连接成功，等待连接断开通知 */
            pthread_mutex_lock(&client->reconnect_lock);
            while (client->connected && client->should_reconnect && g_agent_ctx && g_agent_ctx->running) {
                client->reconnect_notify = false;
                pthread_cond_wait(&client->reconnect_cond, &client->reconnect_lock);
                
                /* 检查是否真的收到断开通知 */
                if (client->reconnect_notify) {
                    LOG_INFO("检测到连接断开，准备重连");
                    break;
                }
            }
            pthread_mutex_unlock(&client->reconnect_lock);
            continue;
        }
        
        if (connecting) {
            sleep(1);
            continue;
        }
        
        if (!g_agent_ctx || !g_agent_ctx->running) {
            break;
        }
        
        sleep(retry_delay);
        
        if (!client->should_reconnect || !g_agent_ctx || !g_agent_ctx->running) {
            break;
        }
        
        /* 解析服务器地址 */
        char host[256];
        int port;
        if (parse_server_addr(client->agent_ctx->config.server_addr, host, sizeof(host), &port) != 0) {
            sleep(retry_delay);
            continue;
        }
        
        /* 执行重连 */
        int ret = do_reconnect(client, host, port);

        pthread_mutex_lock(&client->reconnect_lock);
        if (ret == 0) {
            client->retry_count = 0;
            client->current_retry_delay = client->base_retry_delay;
        } else {
            /* 重连失败，确保 ctx->connected 为 false */
            pthread_mutex_lock(&client->agent_ctx->lock);
            client->agent_ctx->connected = false;
            pthread_mutex_unlock(&client->agent_ctx->lock);

            client->retry_count++;
            client->current_retry_delay = client->current_retry_delay * 2;
            if (client->current_retry_delay > client->max_retry_delay) {
                client->current_retry_delay = client->max_retry_delay;
            }
            LOG_WARN("重连失败 (%d次)，%d秒后重试", client->retry_count, client->current_retry_delay);
        }
        pthread_mutex_unlock(&client->reconnect_lock);
    }
    
    pthread_mutex_lock(&client->reconnect_lock);
    client->reconnect_thread_running = false;
    pthread_mutex_unlock(&client->reconnect_lock);
    
    LOG_INFO("重连线程退出");
    return NULL;
}

/* 启动自动重连 */
/* 停止自动重连 */
void socket_reconnect_stop(void)
{
    if (!g_socket_client) {
        return;
    }
    
    pthread_mutex_lock(&g_socket_client->reconnect_lock);
    g_socket_client->should_reconnect = false;
    pthread_cond_broadcast(&g_socket_client->reconnect_cond);
    pthread_mutex_unlock(&g_socket_client->reconnect_lock);
    
    if (g_socket_client->reconnect_thread_running) {
        pthread_join(g_socket_client->reconnect_thread, NULL);
    }
}

/* 获取连接状态 */
bool socket_is_connected(void)
{
    if (!g_socket_client) {
        return false;
    }
    
    bool connected;
    pthread_mutex_lock(&g_socket_client->reconnect_lock);
    connected = g_socket_client->connected;
    pthread_mutex_unlock(&g_socket_client->reconnect_lock);
    
    return connected;
}

/* 发送JSON消息 */
int socket_send_json(agent_context_t *ctx, msg_type_t type, const char *json)
{
    if (!json) {
        return -1;
    }
    
    return socket_send_message(ctx, type, json, strlen(json));
}

/* 启用自动重连 */
void socket_enable_reconnect(agent_context_t *ctx)
{
    (void)ctx;
    
    if (!g_socket_client) {
        return;
    }
    
    pthread_mutex_lock(&g_socket_client->reconnect_lock);
    g_socket_client->should_reconnect = true;
    g_socket_client->current_retry_delay = g_socket_client->base_retry_delay;
    if (!g_socket_client->reconnect_thread_running) {
        g_socket_client->reconnect_thread_running = true;
        pthread_mutex_unlock(&g_socket_client->reconnect_lock);
        pthread_create(&g_socket_client->reconnect_thread, NULL, socket_reconnect_thread, g_socket_client);
    } else {
        pthread_mutex_unlock(&g_socket_client->reconnect_lock);
    }
}

/* 停止自动重连 */
void socket_disable_reconnect(agent_context_t *ctx)
{
    (void)ctx;
    
    if (!g_socket_client) {
        return;
    }
    
    pthread_mutex_lock(&g_socket_client->reconnect_lock);
    g_socket_client->should_reconnect = false;
    pthread_mutex_unlock(&g_socket_client->reconnect_lock);
}

/* 清理资源 */
void socket_cleanup(void)
{
    socket_reconnect_stop();
    socket_disconnect(NULL);
}
