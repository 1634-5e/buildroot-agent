/*
 * Socket客户端通信模块
 * 使用标准socket + OpenSSL实现TCP客户端
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
#include <openssl/ssl.h>
#include <openssl/err.h>
#include "agent.h"
#include <time.h>

#define CONNECT_TIMEOUT_SEC 30
#define SSL_CONNECT_TIMEOUT_SEC 30
#define MAX_CONNECT_RETRIES 3
#define POLL_TIMEOUT_MS 1000

/* Socket客户端结构 */
typedef struct {
    int sock_fd;                /* Socket文件描述符 */
    SSL *ssl;                   /* SSL连接 */
    SSL_CTX *ssl_ctx;           /* SSL上下文 */
    pthread_t recv_thread;      /* 接收线程 */
    bool thread_running;
    
    /* 发送队列 */
    struct msg_node *msg_head;
    struct msg_node *msg_tail;
    int queued_count;
    pthread_mutex_t send_lock;
    pthread_cond_t send_cond;
    
    /* 连接状态 */
    bool connected;
    bool connecting;
    int retry_count;
    
    agent_context_t *agent_ctx;
} socket_client_t;

/* 消息节点 */
struct msg_node {
    unsigned char *data;
    size_t len;
    struct msg_node *next;
};

static socket_client_t *g_socket_client = NULL;

/* SSL初始化标志 */
static bool g_ssl_initialized = false;

/* 初始化OpenSSL */
static int ssl_init(void)
{
    if (g_ssl_initialized) {
        return 0;
    }
    
    SSL_library_init();
    SSL_load_error_strings();
    OpenSSL_add_all_algorithms();
    g_ssl_initialized = true;
    return 0;
}

/* 清理OpenSSL */
static void ssl_cleanup(void)
{
    if (!g_ssl_initialized) {
        return;
    }
    
    ERR_free_strings();
    EVP_cleanup();
    g_ssl_initialized = false;
}

/* 带超时的连接函数 */
static int connect_with_timeout(int sock_fd, const struct sockaddr *addr, socklen_t addrlen, int timeout_sec)
{
    struct timeval tv;
    
    tv.tv_sec = timeout_sec;
    tv.tv_usec = 0;
    
    if (setsockopt(sock_fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv)) < 0) {
        LOG_WARN("设置连接超时失败: %s", strerror(errno));
    }
    
    while (g_agent_ctx && g_agent_ctx->running) {
        int ret = connect(sock_fd, addr, addrlen);
        if (ret == 0) {
            return 0;
        }
        
        if (errno == EINTR) {
            LOG_DEBUG("connect被信号中断，重试...");
            continue;
        }
        
        return -1;
    }
    
    return -1;
}

/* 带超时的SSL连接函数 */
static int ssl_connect_with_timeout(SSL *ssl, int timeout_sec)
{
    int sock_fd = SSL_get_fd(ssl);
    int flags = fcntl(sock_fd, F_GETFL, 0);
    time_t start_time = time(NULL);
    
    if (fcntl(sock_fd, F_SETFL, flags | O_NONBLOCK) < 0) {
        LOG_ERROR("设置非阻塞模式失败: %s", strerror(errno));
        return -1;
    }
    
    while (g_agent_ctx && g_agent_ctx->running) {
        int ret = SSL_connect(ssl);
        
        if (ret > 0) {
            fcntl(sock_fd, F_SETFL, flags);
            return 0;
        }
        
        int err = SSL_get_error(ssl, ret);
        
        if (err == SSL_ERROR_WANT_READ || err == SSL_ERROR_WANT_WRITE) {
            time_t elapsed = time(NULL) - start_time;
            if (elapsed >= timeout_sec) {
                LOG_ERROR("SSL连接超时");
                fcntl(sock_fd, F_SETFL, flags);
                return -1;
            }
            
            struct pollfd pfd = { .fd = sock_fd, .events = (err == SSL_ERROR_WANT_READ) ? POLLIN : POLLOUT };
            int poll_ret = poll(&pfd, 1, POLL_TIMEOUT_MS);
            
            if (poll_ret < 0) {
                if (errno == EINTR) {
                    continue;
                }
                LOG_ERROR("poll错误: %s", strerror(errno));
                fcntl(sock_fd, F_SETFL, flags);
                return -1;
            } else if (poll_ret == 0) {
                continue;
            }
            
            continue;
        } else {
            LOG_ERROR("SSL连接失败: %d", err);
            ERR_print_errors_fp(stderr);
            fcntl(sock_fd, F_SETFL, flags);
            return -1;
        }
    }
    
    fcntl(sock_fd, F_SETFL, flags);
    return -1;
}

/* 创建SSL上下文 */
static SSL_CTX *create_ssl_context(bool verify_cert)
{
    const SSL_METHOD *method;
    SSL_CTX *ctx;
    
    method = SSLv23_client_method();
    ctx = SSL_CTX_new(method);
    if (!ctx) {
        LOG_ERROR("无法创建SSL上下文");
        return NULL;
    }
    
    if (verify_cert) {
        SSL_CTX_set_verify(ctx, SSL_VERIFY_PEER, NULL);
    } else {
        SSL_CTX_set_verify(ctx, SSL_VERIFY_NONE, NULL);
    }
    
    return ctx;
}

/* 接收线程 */
static void *socket_recv_thread(void *arg)
{
    socket_client_t *client = (socket_client_t *)arg;
    unsigned char recv_buf[65536];
    
    LOG_INFO("Socket接收线程启动");
    
    while (client->thread_running && client->connected) {
        int bytes_received = 0;
        
        if (client->ssl) {
            struct pollfd pfd = { .fd = client->sock_fd, .events = POLLIN };
            int poll_ret = poll(&pfd, 1, POLL_TIMEOUT_MS);
            
            if (poll_ret < 0) {
                if (errno == EINTR) {
                    continue;
                }
                LOG_ERROR("poll错误: %s", strerror(errno));
                break;
            } else if (poll_ret == 0) {
                continue;
            }
            
            bytes_received = SSL_read(client->ssl, recv_buf, sizeof(recv_buf));
        } else {
            bytes_received = recv(client->sock_fd, recv_buf, sizeof(recv_buf), 0);
        }
        
        if (bytes_received <= 0) {
            if (bytes_received == 0) {
                LOG_INFO("服务器关闭连接");
                break;
            } else {
                if (client->ssl) {
                    int ssl_err = SSL_get_error(client->ssl, bytes_received);
                    if (ssl_err == SSL_ERROR_WANT_READ || ssl_err == SSL_ERROR_WANT_WRITE) {
                        continue;
                    }
                    LOG_ERROR("SSL_read错误: %d", ssl_err);
                    break;
                } else {
                    if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
                        continue;
                    }
                    LOG_ERROR("接收数据错误: %s", strerror(errno));
                    break;
                }
            }
        }
        
        LOG_DEBUG("收到数据: %d bytes", bytes_received);
        
        if (client->agent_ctx && bytes_received > 0) {
            protocol_handle_message(client->agent_ctx, (const char *)recv_buf, bytes_received);
        }
    }
    
    LOG_INFO("Socket接收线程退出");
    return NULL;
}

/* 连接到服务器 */
static int do_connect(socket_client_t *client, const char *host, int port, bool use_ssl)
{
    struct sockaddr_in server_addr;
    struct hostent *he;
    int retry = 0;
    
    client->sock_fd = -1;
    
    for (retry = 0; retry < MAX_CONNECT_RETRIES && g_agent_ctx && g_agent_ctx->running; retry++) {
        if (retry > 0) {
            LOG_INFO("重试连接 (%d/%d)...", retry, MAX_CONNECT_RETRIES);
            sleep(client->agent_ctx ? client->agent_ctx->config.reconnect_interval : 5);
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
        
        LOG_INFO("连接到 %s:%d (SSL: %d)", host, port, use_ssl);
        
        if (connect_with_timeout(client->sock_fd, (struct sockaddr *)&server_addr, sizeof(server_addr), CONNECT_TIMEOUT_SEC) < 0) {
            LOG_ERROR("连接失败: %s", strerror(errno));
            close(client->sock_fd);
            client->sock_fd = -1;
            continue;
        }
        
        if (use_ssl) {
            if (ssl_init() != 0) {
                LOG_ERROR("SSL初始化失败");
                close(client->sock_fd);
                client->sock_fd = -1;
                return -1;
            }
            
            client->ssl_ctx = create_ssl_context(false);
            if (!client->ssl_ctx) {
                close(client->sock_fd);
                client->sock_fd = -1;
                return -1;
            }
            
            client->ssl = SSL_new(client->ssl_ctx);
            SSL_set_fd(client->ssl, client->sock_fd);
            
            if (ssl_connect_with_timeout(client->ssl, SSL_CONNECT_TIMEOUT_SEC) != 0) {
                LOG_ERROR("SSL握手失败");
                SSL_free(client->ssl);
                SSL_CTX_free(client->ssl_ctx);
                client->ssl = NULL;
                client->ssl_ctx = NULL;
                close(client->sock_fd);
                client->sock_fd = -1;
                continue;
            }
            
            LOG_INFO("SSL连接建立成功");
        }
        
        return 0;
    }
    
    if (client->sock_fd >= 0) {
        close(client->sock_fd);
        client->sock_fd = -1;
    }
    
    return -1;
}

/* 初始化Socket客户端 */
static socket_client_t *socket_client_init(agent_context_t *ctx)
{
    socket_client_t *client = (socket_client_t *)calloc(1, sizeof(socket_client_t));
    if (!client) {
        LOG_ERROR("内存分配失败");
        return NULL;
    }
    
    client->agent_ctx = ctx;
    pthread_mutex_init(&client->send_lock, NULL);
    pthread_cond_init(&client->send_cond, NULL);
    
    return client;
}

/* 释放Socket客户端 */
static void socket_client_destroy(socket_client_t *client)
{
    if (!client) return;
    
    client->thread_running = false;
    
    if (client->recv_thread) {
        pthread_join(client->recv_thread, NULL);
    }
    
    /* 关闭SSL连接 */
    if (client->ssl) {
        SSL_shutdown(client->ssl);
        SSL_free(client->ssl);
    }
    
    if (client->ssl_ctx) {
        SSL_CTX_free(client->ssl_ctx);
    }
    
    /* 关闭socket */
    if (client->sock_fd >= 0) {
        close(client->sock_fd);
    }
    
    /* 释放发送队列 */
    pthread_mutex_lock(&client->send_lock);
    while (client->msg_head) {
        struct msg_node *node = client->msg_head;
        client->msg_head = node->next;
        free(node->data);
        free(node);
    }
    client->msg_tail = NULL;
    client->queued_count = 0;
    pthread_mutex_unlock(&client->send_lock);
    
    pthread_mutex_destroy(&client->send_lock);
    pthread_cond_destroy(&client->send_cond);
    
    free(client);
}

/* 连接到服务器 */
int socket_connect(agent_context_t *ctx)
{
    if (!ctx) return -1;
    
    /* 首次连接，初始化客户端 */
    if (!g_socket_client) {
        g_socket_client = socket_client_init(ctx);
        if (!g_socket_client) {
            return -1;
        }
        ctx->socket_client = g_socket_client;
    }
    
    socket_client_t *client = g_socket_client;
    
    if (client->connected || client->connecting) {
        LOG_WARN("已经连接或正在连接中");
        return 0;
    }
    
    /* 解析服务器地址 */
    const char *addr = ctx->config.server_addr;
    char host[256] = {0};
    int port = 8766;
    
    /* 解析 host:port */
    char *colon = strchr(addr, ':');
    if (colon) {
        strncpy(host, addr, colon - addr);
        port = atoi(colon + 1);
    } else {
        strncpy(host, addr, sizeof(host) - 1);
    }
    
    if (port <= 0) {
        port = 8766;
    }
    
    client->connecting = true;
    
    /* 连接服务器 */
    if (do_connect(client, host, port, ctx->config.use_ssl) != 0) {
        client->connecting = false;
        return -1;
    }
    
    client->connected = true;
    client->connecting = false;
    client->retry_count = 0;
    
    if (client->agent_ctx) {
        client->agent_ctx->connected = true;
        
        /* 发送认证消息 */
        char *auth_msg = protocol_create_auth_msg(client->agent_ctx);
        if (auth_msg) {
            LOG_DEBUG("发送认证消息: %s", auth_msg);
            int rc = socket_send_json(client->agent_ctx, MSG_TYPE_AUTH, auth_msg);
            if (rc != 0) {
                LOG_ERROR("发送认证消息失败: %d", rc);
            }
            free(auth_msg);
        } else {
            LOG_ERROR("创建认证消息失败");
        }
    }
    
    /* 启动接收线程 */
    client->thread_running = true;
    if (pthread_create(&client->recv_thread, NULL, socket_recv_thread, client) != 0) {
        LOG_ERROR("创建接收线程失败");
        client->thread_running = false;
        socket_disconnect(ctx);
        return -1;
    }
    
    return 0;
}

/* 断开连接 */
void socket_disconnect(agent_context_t *ctx)
{
    if (!g_socket_client) return;
    
    socket_client_t *client = g_socket_client;
    
    client->thread_running = false;
    client->connected = false;
    
    /* 等待接收线程结束 */
    if (client->recv_thread) {
        pthread_join(client->recv_thread, NULL);
        client->recv_thread = 0;
    }
    
    /* 关闭连接 */
    if (client->ssl) {
        SSL_shutdown(client->ssl);
        SSL_free(client->ssl);
        client->ssl = NULL;
    }
    
    if (client->ssl_ctx) {
        SSL_CTX_free(client->ssl_ctx);
        client->ssl_ctx = NULL;
    }
    
    if (client->sock_fd >= 0) {
        close(client->sock_fd);
        client->sock_fd = -1;
    }
    
    if (ctx) {
        ctx->connected = false;
        ctx->authenticated = false;
    }
    
    LOG_INFO("Socket连接已断开");
}

/* 发送消息 */
int socket_send_message(agent_context_t *ctx, msg_type_t type, const char *data, size_t len)
{
    if (!g_socket_client) {
        LOG_WARN("Socket客户端未初始化");
        return -1;
    }
    
    socket_client_t *client = g_socket_client;
    
    /* 检查连接状态 */
    if (!client->connected) {
        LOG_WARN("Socket未连接，跳过发送");
        return -1;
    }
    
    if (len > 65535 - 1) {
        LOG_ERROR("消息太大: %zu > 65534", len);
        return -1;
    }
    
    /* 构建消息 */
    size_t buf_len = 1 + len;
    unsigned char *buf = (unsigned char *)malloc(buf_len);
    if (!buf) {
        LOG_ERROR("内存分配失败");
        return -1;
    }
    
    buf[0] = (unsigned char)type;
    if (data && len > 0) {
        memcpy(buf + 1, data, len);
    }
    
    /* 发送数据 */
    int bytes_sent = 0;
    if (client->ssl) {
        bytes_sent = SSL_write(client->ssl, buf, buf_len);
    } else {
        bytes_sent = send(client->sock_fd, buf, buf_len, 0);
    }
    
    free(buf);
    
    if (bytes_sent != (int)buf_len) {
        LOG_ERROR("发送失败: 期望 %zu, 实际 %d", buf_len, bytes_sent);
        return -1;
    }
    
    LOG_DEBUG("消息已发送: type=0x%02X, len=%zu", type, len);
    return 0;
}

/* 发送JSON消息 */
int socket_send_json(agent_context_t *ctx, msg_type_t type, const char *json)
{
    if (!json) return -1;
    return socket_send_message(ctx, type, json, strlen(json));
}

/* 清理Socket模块 */
void socket_cleanup(void)
{
    if (g_socket_client) {
        socket_client_destroy(g_socket_client);
        g_socket_client = NULL;
    }
    
    ssl_cleanup();
}
