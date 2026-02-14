/*
 * agent_tcp_download.c - TCP文件下载模块（替换libcurl）
 */

#include "agent.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>
#include <pthread.h>
#include <inttypes.h>
#include <stdint.h>
#include <ctype.h>
#include <errno.h>

#define SHA256_DIGEST_LENGTH 32

/* 下载会话状态 */
typedef enum {
    DOWNLOAD_STATE_IDLE = 0,
    DOWNLOAD_STATE_REQUESTED,
    DOWNLOAD_STATE_DOWNLOADING,
    DOWNLOAD_STATE_PAUSED,
    DOWNLOAD_STATE_COMPLETED,
    DOWNLOAD_STATE_ERROR
} download_state_t;

/* 下载会话结构 */
typedef struct download_session {
    char session_id[64];              /* 会话ID */
    char file_path[512];             /* 服务器文件路径 */
    char output_path[512];           /* 本地输出路径 */
    FILE *fp;                        /* 文件句柄 */
    int64_t file_size;               /* 文件总大小 */
    int64_t downloaded;              /* 已下载字节数 */
    int64_t offset;                  /* 当前偏移量 */
    int chunk_size;                  /* 块大小 */
    int timeout;                     /* 超时时间 */
    int max_retries;                 /* 最大重试次数 */
    int retry_count;                 /* 当前重试次数 */
    download_state_t state;          /* 下载状态 */
    progress_callback_t callback;    /* 进度回调 */
    void *user_data;                 /* 用户数据 */
    pthread_mutex_t mutex;           /* 互斥锁 */
    pthread_cond_t cond;             /* 条件变量 - 用于等待下载完成 */
    time_t last_activity;            /* 最后活动时间 */
    struct download_session *next;   /* 链表指针 */
} download_session_t;

/* 全局变量 */
static download_session_t *g_download_sessions = NULL;
static pthread_mutex_t g_sessions_mutex = PTHREAD_MUTEX_INITIALIZER;
static bool g_tcp_download_initialized = false;

/* 生成唯一会话ID */
static void generate_session_id(char *session_id, size_t size) {
    snprintf(session_id, size, "download_%ld_%d", (long)get_timestamp_ms(), rand());
}

/* 查找下载会话 */
static download_session_t *find_session(const char *session_id) {
    download_session_t *session = g_download_sessions;
    while (session) {
        if (strcmp(session->session_id, session_id) == 0) {
            return session;
        }
        session = session->next;
    }
    return NULL;
}

/* 创建下载会话 */
static download_session_t *create_session(const char *file_path, const char *output_path, 
                                         tcp_download_config_t *config) {
    download_session_t *session = (download_session_t *)calloc(1, sizeof(download_session_t));
    if (!session) {
        return NULL;
    }
    
    generate_session_id(session->session_id, sizeof(session->session_id));
    strncpy(session->file_path, file_path, sizeof(session->file_path) - 1);
    strncpy(session->output_path, output_path, sizeof(session->output_path) - 1);
    
    session->offset = 0;
    session->downloaded = 0;
    session->chunk_size = config ? config->chunk_size : 16384;  /* 默认16KB */
    session->timeout = config ? config->timeout : 300;          /* 默认5分钟 */
    session->max_retries = config ? config->max_retries : 3;    /* 默认3次重试 */
    session->retry_count = 0;
    session->state = DOWNLOAD_STATE_IDLE;
    session->callback = config ? config->callback : NULL;
    session->user_data = config ? config->user_data : NULL;
    session->last_activity = time(NULL);
    
    if (pthread_mutex_init(&session->mutex, NULL) != 0) {
        free(session);
        return NULL;
    }
    
    if (pthread_cond_init(&session->cond, NULL) != 0) {
        pthread_mutex_destroy(&session->mutex);
        free(session);
        return NULL;
    }
    
    return session;
}

/* 添加会话到全局列表 */
static void add_session(download_session_t *session) {
    pthread_mutex_lock(&g_sessions_mutex);
    session->next = g_download_sessions;
    g_download_sessions = session;
    pthread_mutex_unlock(&g_sessions_mutex);
}

/* 移除并销毁会话 */
static void remove_session(const char *session_id) {
    pthread_mutex_lock(&g_sessions_mutex);
    download_session_t **current = &g_download_sessions;
    
    while (*current) {
        if (strcmp((*current)->session_id, session_id) == 0) {
            download_session_t *to_remove = *current;
            *current = (*current)->next;
            
            pthread_cond_destroy(&to_remove->cond);
            pthread_mutex_destroy(&to_remove->mutex);
            if (to_remove->fp) {
                fclose(to_remove->fp);
            }
            free(to_remove);
            break;
        }
        current = &(*current)->next;
    }
    pthread_mutex_unlock(&g_sessions_mutex);
}

/* 初始化TCP下载模块 */
int tcp_download_init(void) {
    if (g_tcp_download_initialized) {
        return 0;
    }
    
    srand(time(NULL));
    g_tcp_download_initialized = true;
    LOG_INFO("TCP下载模块初始化成功");
    
    return 0;
}

/* 清理TCP下载模块 */
void tcp_download_cleanup(void) {
    if (!g_tcp_download_initialized) {
        return;
    }
    
    pthread_mutex_lock(&g_sessions_mutex);
    download_session_t *session = g_download_sessions;
    while (session) {
        download_session_t *next = session->next;
        pthread_mutex_destroy(&session->mutex);
        if (session->fp) {
            fclose(session->fp);
        }
        free(session);
        session = next;
    }
    g_download_sessions = NULL;
    pthread_mutex_unlock(&g_sessions_mutex);
    
    g_tcp_download_initialized = false;
    LOG_INFO("TCP下载模块已清理");
}

/* 检查断点续传支持 */
int tcp_can_resume(const char *file_path, const char *output_path) {
    struct stat st;
    if (stat(output_path, &st) != 0) {
        /* 文件不存在，不支持续传 */
        return 0;
    }
    
    /* 文件存在，可以尝试续传 */
    return 1;
}

/* 计算文件SHA256 */
int tcp_calc_sha256(const char *filepath, char *sha256_str)
{
    if (!filepath || !sha256_str) {
        return -1;
    }
    
    /* 使用系统 sha256sum 命令 */
    char cmd[512];
    snprintf(cmd, sizeof(cmd), "sha256sum \"%s\"", filepath);
    
    FILE *fp = popen(cmd, "r");
    if (!fp) {
        LOG_ERROR("无法执行sha256sum命令: %s", strerror(errno));
        return -1;
    }
    
    /* sha256sum 输出格式: "e3b0c44298f1b7192a1d8f35a6c6a8a3a9b2c1b7c9e8c8c3c5a6  filename" */
    char output[128];
    if (fgets(output, sizeof(output), fp)) {
        /* 提取空格前的校验和 */
        char *space_pos = strchr(output, ' ');
        if (space_pos) {
            *space_pos = '\0';
        }
        strncpy(sha256_str, output, 64);
        sha256_str[64] = '\0';
    } else {
        LOG_ERROR("无法读取sha256sum输出");
        pclose(fp);
        return -1;
    }
    
    pclose(fp);
    return 0;
}

/* 验证SHA256校验和 */
bool tcp_verify_checksum(const char *filepath, const char *expected_sha256)
{
    if (!filepath) {
        return false;
    }
    
    if (!expected_sha256 || strlen(expected_sha256) == 0) {
        return true;  /* 没有提供期望值，跳过校验 */
    }
    
    /* 校验SHA256 */
    char actual_sha256[SHA256_DIGEST_LENGTH * 2 + 1];
    if (tcp_calc_sha256(filepath, actual_sha256) == 0) {
        if (strcmp(actual_sha256, expected_sha256) != 0) {
            LOG_ERROR("SHA256校验失败: 期望 %s, 实际 %s", 
                     expected_sha256, actual_sha256);
            return false;
        }
        LOG_INFO("SHA256校验通过: %s", actual_sha256);
        return true;
    } else {
        LOG_ERROR("SHA256计算失败");
        return false;
    }
}

/* 启动文件下载 */
int tcp_download_file(agent_context_t *ctx, const char *file_path, const char *output_path, tcp_download_config_t *config) {
    if (!file_path || !output_path) {
        LOG_ERROR("文件路径或输出路径为空");
        return -1;
    }
    
    if (!g_tcp_download_initialized) {
        LOG_ERROR("TCP下载模块未初始化");
        return -1;
    }
    
    LOG_INFO("开始TCP下载: %s -> %s", file_path, output_path);
    
    /* 创建下载会话 */
    download_session_t *session = create_session(file_path, output_path, config);
    if (!session) {
        LOG_ERROR("创建下载会话失败");
        return -1;
    }
    
    /* 检查断点续传 */
    struct stat st;
    if (stat(output_path, &st) == 0) {
        session->offset = st.st_size;
        session->downloaded = st.st_size;
        session->fp = fopen(output_path, "ab");  /* 追加模式 */
        LOG_INFO("断点续传: 从位置 %lld", (long long)session->offset);
    } else {
        session->fp = fopen(output_path, "wb");  /* 新建模式 */
    }
    
    if (!session->fp) {
        LOG_ERROR("无法打开输出文件: %s", output_path);
        free(session);
        return -1;
    }
    
    /* 添加到全局会话列表 */
    add_session(session);
    session->state = DOWNLOAD_STATE_REQUESTED;
    
    /* 构造下载请求JSON */
    char request_json[1024];
    snprintf(request_json, sizeof(request_json),
             "{\"action\":\"download_update\","
             "\"file_path\":\"%s\","
             "\"offset\":%lld,"
             "\"chunk_size\":%d,"
             "\"request_id\":\"%s\"}",
             file_path, (long long)session->offset, session->chunk_size, session->session_id);
    
    /* 发送下载请求到服务器 */
    if (ctx) {
        int rc = socket_send_json(ctx, MSG_TYPE_FILE_DOWNLOAD_REQUEST, request_json);
        if (rc != 0) {
            LOG_ERROR("发送下载请求失败");
            remove_session(session->session_id);
            return -1;
        }
    } else {
        LOG_ERROR("Agent上下文为空，无法发送请求");
        remove_session(session->session_id);
        return -1;
    }
    
    LOG_INFO("下载请求已发送，会话ID: %s", session->session_id);

    /* 等待下载完成 */
    LOG_INFO("等待下载完成，初始状态=%d", session->state);
    pthread_mutex_lock(&session->mutex);
    LOG_DEBUG("已获取mutex，开始等待条件变量");

    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    ts.tv_sec += 300; /* 5分钟超时 */

    int wait_count = 0;
    while (session->state != DOWNLOAD_STATE_COMPLETED &&
           session->state != DOWNLOAD_STATE_ERROR) {
        LOG_DEBUG("等待条件变量[%d], 当前状态=%d", ++wait_count, session->state);
        int rc = pthread_cond_timedwait(&session->cond, &session->mutex, &ts);
        if (rc == ETIMEDOUT) {
            LOG_ERROR("下载等待超时（5分钟），当前状态=%d", session->state);
            session->state = DOWNLOAD_STATE_ERROR;
            pthread_mutex_unlock(&session->mutex);
            remove_session(session->session_id);
            return -1;
        } else if (rc != 0) {
            LOG_ERROR("条件变量等待错误: %s (rc=%d)", strerror(rc), rc);
            pthread_mutex_unlock(&session->mutex);
            remove_session(session->session_id);
            return -1;
        }
        LOG_DEBUG("条件变量被触发，当前状态=%d", session->state);
    }
    pthread_mutex_unlock(&session->mutex);
    LOG_INFO("下载等待结束，最终状态=%d (COMPLETED=%d, ERROR=%d)",
             session->state, DOWNLOAD_STATE_COMPLETED, DOWNLOAD_STATE_ERROR);
    
    /* 检查下载结果 */
    if (session->state == DOWNLOAD_STATE_ERROR) {
        LOG_ERROR("下载过程中发生错误");
        remove_session(session->session_id);
        return -1;
    }
    
    LOG_INFO("下载完成: %s", session->output_path);
    return 0;
}

/* 处理下载响应数据 */
int tcp_handle_download_response(agent_context_t *ctx, const char *data, size_t len) {
    if (!data || len == 0) {
        return -1;
    }
    
    /* 解析JSON响应 */
    char *action = json_get_string(data, "action");
    if (!action) {
        LOG_ERROR("下载响应缺少action字段");
        return -1;
    }
    
    LOG_DEBUG("处理下载响应: action=%s", action);
    
    if (strcmp(action, "file_data") == 0) {
        /* 处理文件数据块 */
        char *session_id = json_get_string(data, "request_id");
        char *file_path = json_get_string(data, "file_path");
        long long offset = json_get_int64(data, "offset");
        char *data_b64 = json_get_string(data, "data");
        int data_size = json_get_int(data, "size", 0);
        bool is_final = json_get_bool(data, "is_final", false);
        long long total_size = json_get_int64(data, "total_size");

        LOG_DEBUG("收到文件数据块: session_id=%s, offset=%lld, size=%d, is_final=%d, total_size=%lld",
                  session_id ? session_id : "null", (long long)offset, data_size, is_final, (long long)total_size);
        
        if (!session_id || !file_path || !data_b64) {
            LOG_ERROR("下载响应缺少必要字段");
            return -1;
        }
        
        /* 查找对应的下载会话 */
        download_session_t *session = find_session(session_id);
        if (!session) {
            LOG_ERROR("未找到下载会话: %s", session_id);
            return -1;
        }
        
        pthread_mutex_lock(&session->mutex);
        
        /* 更新文件大小信息 - 始终设置以确保一致性 */
        if (total_size > 0) {
            if (session->file_size == 0) {
                LOG_INFO("文件总大小: %lld 字节", (long long)total_size);
            }
            session->file_size = total_size;
            LOG_DEBUG("设置文件大小: file_size=%lld", (long long)session->file_size);
        }
        
        /* 验证偏移量 */
        if (offset != session->offset) {
            LOG_ERROR("数据块偏移量不匹配: 期望 %lld, 收到 %lld", 
                     (long long)session->offset, (long long)offset);
            pthread_mutex_unlock(&session->mutex);
            return -1;
        }
        
        /* 解码Base64数据并写入文件 */
        unsigned char decoded_data[data_size];
        size_t decoded_len = base64_decode(data_b64, decoded_data);
        
        if (decoded_len != data_size) {
            LOG_ERROR("Base64解码失败: 期望 %d 字节, 实际 %zu 字节", data_size, decoded_len);
            pthread_mutex_unlock(&session->mutex);
            return -1;
        }
        
        /* 写入文件 */
        if (fwrite(decoded_data, 1, decoded_len, session->fp) != decoded_len) {
            LOG_ERROR("写入文件失败");
            pthread_mutex_unlock(&session->mutex);
            return -1;
        }
        
        /* 更新下载进度 */
        session->offset += data_size;
        session->downloaded += data_size;
        session->last_activity = time(NULL);
        
        /* 调用进度回调 */
        if (session->callback && session->file_size > 0) {
            int progress = (int)((session->downloaded * 100) / session->file_size);
            session->callback(session->file_path, progress, session->downloaded, 
                             session->file_size, session->user_data);
        }
        
        /* 检查是否完成 */
        LOG_DEBUG("检查下载完成: is_final=%d, downloaded=%lld, file_size=%lld, offset=%lld, actual_size=%d",
                  is_final, (long long)session->downloaded, (long long)session->file_size,
                  (long long)offset, data_size);
        if (is_final || (session->file_size > 0 && session->downloaded >= session->file_size)) {
            LOG_INFO("下载完成条件满足: is_final=%d, downloaded=%lld/%lld",
                     is_final, (long long)session->downloaded, (long long)session->file_size);
            session->state = DOWNLOAD_STATE_COMPLETED;
            fclose(session->fp);
            session->fp = NULL;

            LOG_INFO("下载完成: %s", session->output_path);
            LOG_INFO("下载状态: 已下载 %lld / %lld 字节",
                     (long long)session->downloaded, (long long)session->file_size);

            /* 最终进度回调 */
            if (session->callback) {
                LOG_DEBUG("调用最终进度回调");
                session->callback(session->file_path, 100, session->downloaded,
                                 session->file_size, session->user_data);
            }

            LOG_DEBUG("设置状态为COMPLETED=%d，准备发送条件信号", DOWNLOAD_STATE_COMPLETED);
            /* 通知等待的线程 */
            pthread_cond_signal(&session->cond);
            LOG_DEBUG("条件信号已发送");
            pthread_mutex_unlock(&session->mutex);
            LOG_DEBUG("下载完成处理结束，mutex已释放");
        } else {
            session->state = DOWNLOAD_STATE_DOWNLOADING;
            pthread_mutex_unlock(&session->mutex);

            /* 请求下一个数据块 */
            char next_request[1024];
            snprintf(next_request, sizeof(next_request),
                     "{\"action\":\"download_update\","
                     "\"file_path\":\"%s\","
                     "\"offset\":%lld,"
                     "\"chunk_size\":%d,"
                     "\"request_id\":\"%s\"}",
                     file_path, (long long)session->offset, session->chunk_size, session_id);

            /* 发送下一个数据块请求 */
            int send_rc = socket_send_json(ctx, MSG_TYPE_FILE_DOWNLOAD_REQUEST, next_request);
            if (send_rc != 0) {
                LOG_ERROR("发送下一个数据块请求失败: rc=%d", send_rc);
            } else {
                LOG_DEBUG("已发送下一个数据块请求: offset=%lld", (long long)session->offset);
            }
        }
        
    } else if (strcmp(action, "download_error") == 0) {
        /* 处理下载错误 */
        char *session_id = json_get_string(data, "request_id");
        char *error_msg = json_get_string(data, "error");
        
        if (session_id) {
            download_session_t *session = find_session(session_id);
            if (session) {
                pthread_mutex_lock(&session->mutex);
                session->state = DOWNLOAD_STATE_ERROR;
                LOG_ERROR("下载错误: %s", error_msg ? error_msg : "未知错误");
                pthread_cond_signal(&session->cond);
                pthread_mutex_unlock(&session->mutex);
            }
        }
    }
    
    free(action);
    return 0;
}