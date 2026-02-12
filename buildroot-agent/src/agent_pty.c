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
#include <time.h>

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
    
    LOG_INFO("PTY读取线程启动: session_id=%d, fd=%d", session->session_id, session->master_fd);
    
    while (session->active) {
        /* 检查文件描述符有效性 */
        if (session->master_fd < 0) {
            LOG_ERROR("PTY文件描述符无效: fd=%d", session->master_fd);
            break;
        }
        
        /* 使用非阻塞读取，避免select的FD_SETSIZE限制 */
        ssize_t n = read(session->master_fd, buf, sizeof(buf) - 1);
        
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                /* 非阻塞模式下没有数据可读，短暂休眠 */
                usleep(10000);  /* 10ms - 更少延迟 */
                continue;
            } else if (errno == EINTR) {
                continue;
            } else {
                LOG_ERROR("PTY读取错误: fd=%d, %s", session->master_fd, strerror(errno));
                break;
            }
        } else if (n == 0) {
            /* EOF - 连接关闭 */
            LOG_INFO("PTY连接关闭: session_id=%d", session->session_id);
            break;
        }
        
        /* 确保字符串结束 */
        buf[n] = '\0';
        LOG_INFO("PTY读取: session_id=%d, bytes=%zd", session->session_id, n);
        
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
                    struct timespec _ts_enqueue;
                    clock_gettime(CLOCK_REALTIME, &_ts_enqueue);
                    LOG_INFO("发送 PTY_DATA 入队: session_id=%d, encoded_len=%zu, ts=%ld.%09ld", session->session_id, encoded_len, (long)_ts_enqueue.tv_sec, _ts_enqueue.tv_nsec);
                    int send_result = socket_send_json(ctx, MSG_TYPE_PTY_DATA, json);
                    if (send_result != 0) {
                        LOG_WARN("PTY数据发送失败，session_id=%d", session->session_id);
                    } else {
                        struct timespec _ts_sentok;
                        clock_gettime(CLOCK_REALTIME, &_ts_sentok);
                        LOG_INFO("PTY_DATA 已成功入队发送: session_id=%d, ts=%ld.%09ld", session->session_id, (long)_ts_sentok.tv_sec, _ts_sentok.tv_nsec);
                    }
                    free(json);
                }
                free(encoded);
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
        socket_send_json(ctx, MSG_TYPE_PTY_CLOSE, json);
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
    session->master_fd = -1;  /* 初始化为无效值 */
    session->child_pid = -1;
    session->active = false;
    
    /* 创建伪终端 */
    int master_fd;
    
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
        
        /* 设置环境变量 - 确保UTF-8编码 */
        setenv("TERM", "xterm-256color", 1);
        setenv("LANG", "en_US.UTF-8", 1);
        setenv("LC_ALL", "en_US.UTF-8", 1);
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
    
    /* 检查文件描述符有效性 (移除FD_SETSIZE检查，因为不再使用select) */
    if (master_fd < 0) {
        LOG_ERROR("PTY master文件描述符无效: fd=%d", master_fd);
        close(master_fd);
        kill(pid, SIGKILL);
        waitpid(pid, NULL, 0);
        pthread_mutex_unlock(&g_pty_lock);
        return -1;
    }
    
    /* 父进程 */
    session->master_fd = master_fd;
    session->child_pid = pid;
    session->active = true;
    
    /* 设置非阻塞模式 */
    int flags = fcntl(master_fd, F_GETFL, 0);
    if (flags < 0) {
        LOG_ERROR("获取文件描述符标志失败: %s", strerror(errno));
        close(master_fd);
        kill(pid, SIGKILL);
        waitpid(pid, NULL, 0);
        session->active = false;
        pthread_mutex_unlock(&g_pty_lock);
        return -1;
    }
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
    
    LOG_INFO("PTY会话已创建: session_id=%d, pid=%d, fd=%d, size=%dx%d", 
             session_id, pid, master_fd, session->cols, session->rows);
    
    /* 发送创建成功消息 */
    char json[256];
    snprintf(json, sizeof(json),
        "{\"session_id\":%d,\"status\":\"created\",\"rows\":%d,\"cols\":%d}",
        session_id, session->rows, session->cols);
    socket_send_json(ctx, MSG_TYPE_PTY_CREATE, json);
    
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
    
    /* 检查会话状态和文件描述符 */
    if (!session->active || session->master_fd < 0) {
        pthread_mutex_unlock(&g_pty_lock);
        LOG_WARN("PTY会话未活跃或文件描述符无效: session_id=%d", session_id);
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
    LOG_DEBUG("PTY写入: session_id=%d, decoded_len=%zu", session_id, decoded_len);
    
    /* 写入PTY */
    ssize_t written = write(session->master_fd, decoded, decoded_len);
    free(decoded);
    
    if (written < 0) {
        LOG_ERROR("PTY写入失败: fd=%d, %s", session->master_fd, strerror(errno));
        return -1;
    }
    
    if (written != (ssize_t)decoded_len) {
        LOG_WARN("PTY写入不完整: 期望%zu字节，实际写入%zd字节", decoded_len, written);
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
    
    /* 检查会话状态和文件描述符 */
    if (!session->active || session->master_fd < 0) {
        pthread_mutex_unlock(&g_pty_lock);
        LOG_WARN("PTY会话未活跃或文件描述符无效: session_id=%d", session_id);
        return -1;
    }
    
    struct winsize ws;
    ws.ws_row = rows > 0 ? rows : 24;
    ws.ws_col = cols > 0 ? cols : 80;
    ws.ws_xpixel = 0;
    ws.ws_ypixel = 0;
    
    if (ioctl(session->master_fd, TIOCSWINSZ, &ws) < 0) {
        pthread_mutex_unlock(&g_pty_lock);
        LOG_ERROR("设置PTY窗口大小失败: fd=%d, %s", session->master_fd, strerror(errno));
        return -1;
    }
    
    session->rows = ws.ws_row;
    session->cols = ws.ws_col;
    
    /* 发送SIGWINCH信号 */
    if (session->child_pid > 0) {
        kill(session->child_pid, SIGWINCH);
    }
    
    pthread_mutex_unlock(&g_pty_lock);
    
    LOG_INFO("PTY窗口大小已调整: session_id=%d, size=%dx%d", session_id, ws.ws_col, ws.ws_row);
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
    
    LOG_INFO("关闭PTY会话: session_id=%d, fd=%d, pid=%d", 
             session_id, session->master_fd, session->child_pid);
    
    /* 先标记为非活跃，让读取线程退出 */
    session->active = false;
    
    /* 关闭master fd */
    if (session->master_fd >= 0) {
        close(session->master_fd);
        session->master_fd = -1;
    }
    
    /* 终止子进程 */
    if (session->child_pid > 0) {
        /* 发送SIGHUP信号 */
        kill(session->child_pid, SIGHUP);
        usleep(100000);  /* 等待100ms */
        
        /* 检查进程是否还存在 */
        int status;
        if (waitpid(session->child_pid, &status, WNOHANG) == 0) {
            /* 进程仍在运行，发送SIGKILL */
            kill(session->child_pid, SIGKILL);
            waitpid(session->child_pid, NULL, 0);
        }
        session->child_pid = -1;
    }
    
    /* 等待读取线程结束 */
    if (session->read_thread) {
        pthread_join(session->read_thread, NULL);
        session->read_thread = 0;
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
            LOG_INFO("清理PTY会话: session_id=%d, fd=%d, pid=%d", 
                     g_pty_sessions[i].session_id, 
                     g_pty_sessions[i].master_fd, 
                     g_pty_sessions[i].child_pid);
            
            /* 标记为非活跃 */
            g_pty_sessions[i].active = false;
            
            /* 关闭文件描述符 */
            if (g_pty_sessions[i].master_fd >= 0) {
                close(g_pty_sessions[i].master_fd);
                g_pty_sessions[i].master_fd = -1;
            }
            
            /* 终止子进程 */
            if (g_pty_sessions[i].child_pid > 0) {
                kill(g_pty_sessions[i].child_pid, SIGHUP);
                usleep(50000);  /* 等待50ms */
                kill(g_pty_sessions[i].child_pid, SIGKILL);
                waitpid(g_pty_sessions[i].child_pid, NULL, 0);
                g_pty_sessions[i].child_pid = -1;
            }
            
            /* 等待线程结束 */
            if (g_pty_sessions[i].read_thread) {
                pthread_join(g_pty_sessions[i].read_thread, NULL);
                g_pty_sessions[i].read_thread = 0;
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
    socket_send_json(ctx, MSG_TYPE_CMD_RESPONSE, json);
    
    return 0;
}
