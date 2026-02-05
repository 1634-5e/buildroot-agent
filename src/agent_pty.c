/*
 * 交互式Shell (PTY) 模块
 * 使用伪终端实现远程交互式命令行
 */

#define _XOPEN_SOURCE 600
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <signal.h>
#include <pthread.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <pty.h>
#include "agent.h"

#define MAX_PTY_SESSIONS    8
#define PTY_READ_BUF_SIZE   4096

/* PTY会话数组 */
static pty_session_t g_pty_sessions[MAX_PTY_SESSIONS];
static pthread_mutex_t g_pty_lock = PTHREAD_MUTEX_INITIALIZER;

/* Base64编码用于二进制数据传输 */
static const char base64_chars[] = 
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static char *base64_encode_pty(const unsigned char *data, size_t len, size_t *out_len)
{
    *out_len = 4 * ((len + 2) / 3);
    char *encoded = malloc(*out_len + 1);
    if (!encoded) return NULL;
    
    size_t i, j;
    for (i = 0, j = 0; i < len;) {
        uint32_t a = i < len ? data[i++] : 0;
        uint32_t b = i < len ? data[i++] : 0;
        uint32_t c = i < len ? data[i++] : 0;
        uint32_t triple = (a << 16) + (b << 8) + c;
        
        encoded[j++] = base64_chars[(triple >> 18) & 0x3F];
        encoded[j++] = base64_chars[(triple >> 12) & 0x3F];
        encoded[j++] = base64_chars[(triple >> 6) & 0x3F];
        encoded[j++] = base64_chars[triple & 0x3F];
    }
    
    int mod = len % 3;
    if (mod > 0) {
        for (i = 0; i < (size_t)(3 - mod); i++) {
            encoded[*out_len - 1 - i] = '=';
        }
    }
    
    encoded[*out_len] = '\0';
    return encoded;
}

/* Base64解码 */
static int base64_decode_char(char c)
{
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '+') return 62;
    if (c == '/') return 63;
    return -1;
}

static unsigned char *base64_decode_pty(const char *data, size_t len, size_t *out_len)
{
    if (len % 4 != 0) return NULL;
    
    *out_len = len / 4 * 3;
    if (data[len - 1] == '=') (*out_len)--;
    if (data[len - 2] == '=') (*out_len)--;
    
    unsigned char *decoded = malloc(*out_len);
    if (!decoded) return NULL;
    
    size_t i, j;
    for (i = 0, j = 0; i < len;) {
        int a = base64_decode_char(data[i++]);
        int b = base64_decode_char(data[i++]);
        int c = data[i] == '=' ? 0 : base64_decode_char(data[i]); i++;
        int d = data[i] == '=' ? 0 : base64_decode_char(data[i]); i++;
        
        if (a < 0 || b < 0) {
            free(decoded);
            return NULL;
        }
        
        uint32_t triple = (a << 18) + (b << 12) + (c << 6) + d;
        
        if (j < *out_len) decoded[j++] = (triple >> 16) & 0xFF;
        if (j < *out_len) decoded[j++] = (triple >> 8) & 0xFF;
        if (j < *out_len) decoded[j++] = triple & 0xFF;
    }
    
    return decoded;
}

/* 查找PTY会话 */
static pty_session_t *find_pty_session(int session_id)
{
    for (int i = 0; i < MAX_PTY_SESSIONS; i++) {
        if (g_pty_sessions[i].active && g_pty_sessions[i].session_id == session_id) {
            return &g_pty_sessions[i];
        }
    }
    return NULL;
}

/* 查找空闲PTY槽位 */
static pty_session_t *find_free_pty_slot(void)
{
    for (int i = 0; i < MAX_PTY_SESSIONS; i++) {
        if (!g_pty_sessions[i].active) {
            return &g_pty_sessions[i];
        }
    }
    return NULL;
}

/* PTY读取线程 - 从PTY读取数据并发送到云端 */
static void *pty_read_thread(void *arg)
{
    pty_session_t *session = (pty_session_t *)arg;
    agent_context_t *ctx = g_agent_ctx;
    
    char buf[PTY_READ_BUF_SIZE];
    
    LOG_INFO("PTY读取线程启动: session_id=%d", session->session_id);
    
    while (session->active) {
        fd_set rfds;
        struct timeval tv;
        
        FD_ZERO(&rfds);
        FD_SET(session->master_fd, &rfds);
        
        tv.tv_sec = 0;
        tv.tv_usec = 100000;  /* 100ms超时 */
        
        int ret = select(session->master_fd + 1, &rfds, NULL, NULL, &tv);
        
        if (ret < 0) {
            if (errno == EINTR) continue;
            LOG_ERROR("PTY select错误: %s", strerror(errno));
            break;
        }
        
        if (ret == 0) continue;  /* 超时 */
        
        if (FD_ISSET(session->master_fd, &rfds)) {
            ssize_t n = read(session->master_fd, buf, sizeof(buf));
            
            if (n <= 0) {
                if (n < 0 && errno == EAGAIN) continue;
                LOG_INFO("PTY读取结束: session_id=%d", session->session_id);
                break;
            }
            
            /* Base64编码并发送 */
            if (ctx && ctx->connected) {
                size_t encoded_len;
                char *encoded = base64_encode_pty((unsigned char *)buf, n, &encoded_len);
                if (encoded) {
                    char *json = malloc(encoded_len + 256);
                    if (json) {
                        snprintf(json, encoded_len + 256,
                            "{\"session_id\":%d,\"data\":\"%s\"}",
                            session->session_id, encoded);
                        ws_send_json(ctx, MSG_TYPE_PTY_DATA, json);
                        free(json);
                    }
                    free(encoded);
                }
            }
        }
    }
    
    /* 关闭会话 */
    session->active = false;
    
    /* 通知云端会话已关闭 */
    if (ctx && ctx->connected) {
        char json[128];
        snprintf(json, sizeof(json), 
            "{\"session_id\":%d,\"reason\":\"closed\"}", session->session_id);
        ws_send_json(ctx, MSG_TYPE_PTY_CLOSE, json);
    }
    
    LOG_INFO("PTY读取线程退出: session_id=%d", session->session_id);
    return NULL;
}

/* 创建PTY会话 */
int pty_create_session(agent_context_t *ctx, int session_id, int rows, int cols)
{
    if (!ctx) return -1;
    
    if (!ctx->config.enable_pty) {
        LOG_WARN("PTY功能已禁用");
        return -1;
    }
    
    pthread_mutex_lock(&g_pty_lock);
    
    /* 检查是否已存在 */
    if (find_pty_session(session_id) != NULL) {
        pthread_mutex_unlock(&g_pty_lock);
        LOG_WARN("PTY会话已存在: %d", session_id);
        return -1;
    }
    
    /* 查找空闲槽位 */
    pty_session_t *session = find_free_pty_slot();
    if (!session) {
        pthread_mutex_unlock(&g_pty_lock);
        LOG_ERROR("PTY会话数已达上限");
        return -1;
    }
    
    /* 初始化会话 */
    memset(session, 0, sizeof(pty_session_t));
    session->session_id = session_id;
    session->rows = rows > 0 ? rows : 24;
    session->cols = cols > 0 ? cols : 80;
    
    /* 创建伪终端 */
    int master_fd, slave_fd;
    
    struct winsize ws;
    ws.ws_row = session->rows;
    ws.ws_col = session->cols;
    ws.ws_xpixel = 0;
    ws.ws_ypixel = 0;
    
    pid_t pid = forkpty(&master_fd, NULL, NULL, &ws);
    
    if (pid < 0) {
        pthread_mutex_unlock(&g_pty_lock);
        LOG_ERROR("forkpty失败: %s", strerror(errno));
        return -1;
    }
    
    if (pid == 0) {
        /* 子进程 - 执行shell */
        
        /* 设置环境变量 */
        setenv("TERM", "xterm-256color", 1);
        setenv("PATH", "/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin", 1);
        setenv("HOME", "/root", 1);
        setenv("SHELL", "/bin/sh", 1);
        
        /* 切换到home目录 */
        chdir("/root");
        
        /* 执行shell */
        const char *shell = getenv("SHELL");
        if (!shell) shell = "/bin/sh";
        
        execlp(shell, shell, "-i", NULL);
        
        /* exec失败 */
        perror("exec shell failed");
        _exit(127);
    }
    
    /* 父进程 */
    session->master_fd = master_fd;
    session->child_pid = pid;
    session->active = true;
    
    /* 设置非阻塞模式 */
    int flags = fcntl(master_fd, F_GETFL, 0);
    fcntl(master_fd, F_SETFL, flags | O_NONBLOCK);
    
    /* 启动读取线程 */
    if (pthread_create(&session->read_thread, NULL, pty_read_thread, session) != 0) {
        LOG_ERROR("创建PTY读取线程失败");
        close(master_fd);
        kill(pid, SIGKILL);
        waitpid(pid, NULL, 0);
        session->active = false;
        pthread_mutex_unlock(&g_pty_lock);
        return -1;
    }
    
    pthread_mutex_unlock(&g_pty_lock);
    
    LOG_INFO("PTY会话已创建: session_id=%d, pid=%d, size=%dx%d", 
             session_id, pid, session->cols, session->rows);
    
    /* 发送创建成功消息 */
    char json[256];
    snprintf(json, sizeof(json),
        "{\"session_id\":%d,\"status\":\"created\",\"rows\":%d,\"cols\":%d}",
        session_id, session->rows, session->cols);
    ws_send_json(ctx, MSG_TYPE_PTY_CREATE, json);
    
    return 0;
}

/* 向PTY写入数据 */
int pty_write_data(agent_context_t *ctx, int session_id, const char *data, size_t len)
{
    pthread_mutex_lock(&g_pty_lock);
    
    pty_session_t *session = find_pty_session(session_id);
    if (!session) {
        pthread_mutex_unlock(&g_pty_lock);
        LOG_WARN("PTY会话不存在: %d", session_id);
        return -1;
    }
    
    /* Base64解码 */
    size_t decoded_len;
    unsigned char *decoded = base64_decode_pty(data, len, &decoded_len);
    
    pthread_mutex_unlock(&g_pty_lock);
    
    if (!decoded) {
        LOG_ERROR("Base64解码失败");
        return -1;
    }
    
    /* 写入PTY */
    ssize_t written = write(session->master_fd, decoded, decoded_len);
    free(decoded);
    
    if (written < 0) {
        LOG_ERROR("PTY写入失败: %s", strerror(errno));
        return -1;
    }
    
    return 0;
}

/* 调整PTY窗口大小 */
int pty_resize(agent_context_t *ctx, int session_id, int rows, int cols)
{
    pthread_mutex_lock(&g_pty_lock);
    
    pty_session_t *session = find_pty_session(session_id);
    if (!session) {
        pthread_mutex_unlock(&g_pty_lock);
        LOG_WARN("PTY会话不存在: %d", session_id);
        return -1;
    }
    
    struct winsize ws;
    ws.ws_row = rows;
    ws.ws_col = cols;
    ws.ws_xpixel = 0;
    ws.ws_ypixel = 0;
    
    if (ioctl(session->master_fd, TIOCSWINSZ, &ws) < 0) {
        pthread_mutex_unlock(&g_pty_lock);
        LOG_ERROR("设置PTY窗口大小失败: %s", strerror(errno));
        return -1;
    }
    
    session->rows = rows;
    session->cols = cols;
    
    /* 发送SIGWINCH信号 */
    kill(session->child_pid, SIGWINCH);
    
    pthread_mutex_unlock(&g_pty_lock);
    
    LOG_INFO("PTY窗口大小已调整: session_id=%d, size=%dx%d", session_id, cols, rows);
    return 0;
}

/* 关闭PTY会话 */
int pty_close_session(agent_context_t *ctx, int session_id)
{
    pthread_mutex_lock(&g_pty_lock);
    
    pty_session_t *session = find_pty_session(session_id);
    if (!session) {
        pthread_mutex_unlock(&g_pty_lock);
        return 0;
    }
    
    LOG_INFO("关闭PTY会话: session_id=%d", session_id);
    
    session->active = false;
    
    /* 关闭master fd */
    if (session->master_fd >= 0) {
        close(session->master_fd);
        session->master_fd = -1;
    }
    
    /* 终止子进程 */
    if (session->child_pid > 0) {
        kill(session->child_pid, SIGHUP);
        usleep(100000);  /* 等待100ms */
        kill(session->child_pid, SIGKILL);
        waitpid(session->child_pid, NULL, WNOHANG);
        session->child_pid = 0;
    }
    
    pthread_mutex_unlock(&g_pty_lock);
    
    return 0;
}

/* 清理所有PTY会话 */
void pty_cleanup_all(agent_context_t *ctx)
{
    LOG_INFO("清理所有PTY会话");
    
    pthread_mutex_lock(&g_pty_lock);
    
    for (int i = 0; i < MAX_PTY_SESSIONS; i++) {
        if (g_pty_sessions[i].active) {
            g_pty_sessions[i].active = false;
            
            if (g_pty_sessions[i].master_fd >= 0) {
                close(g_pty_sessions[i].master_fd);
            }
            
            if (g_pty_sessions[i].child_pid > 0) {
                kill(g_pty_sessions[i].child_pid, SIGKILL);
                waitpid(g_pty_sessions[i].child_pid, NULL, WNOHANG);
            }
        }
    }
    
    pthread_mutex_unlock(&g_pty_lock);
}

/* 获取活跃的PTY会话列表 */
int pty_list_sessions(agent_context_t *ctx)
{
    if (!ctx) return -1;
    
    pthread_mutex_lock(&g_pty_lock);
    
    char json[1024];
    int offset = snprintf(json, sizeof(json), "{\"sessions\":[");
    int count = 0;
    
    for (int i = 0; i < MAX_PTY_SESSIONS; i++) {
        if (g_pty_sessions[i].active) {
            offset += snprintf(json + offset, sizeof(json) - offset,
                "%s{\"session_id\":%d,\"pid\":%d,\"rows\":%d,\"cols\":%d}",
                count > 0 ? "," : "",
                g_pty_sessions[i].session_id,
                g_pty_sessions[i].child_pid,
                g_pty_sessions[i].rows,
                g_pty_sessions[i].cols);
            count++;
        }
    }
    
    pthread_mutex_unlock(&g_pty_lock);
    
    snprintf(json + offset, sizeof(json) - offset, "],\"count\":%d}", count);
    ws_send_json(ctx, MSG_TYPE_CMD_RESPONSE, json);
    
    return 0;
}
