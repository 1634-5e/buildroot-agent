/*
 * 日志上报模块
 * 支持上传日志文件、tail跟踪、实时监控
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/inotify.h>
#include <pthread.h>
#include <dirent.h>
#include <errno.h>
#include "agent.h"

#define MAX_LOG_WATCHES     16
#define LOG_CHUNK_SIZE      (32 * 1024)  /* 32KB per chunk */
#define INOTIFY_BUF_SIZE    4096

/* 日志监控结构 */
typedef struct {
    char filepath[256];
    int watch_fd;
    off_t last_pos;
    bool active;
    pthread_t thread;
    agent_context_t *ctx;
} log_watch_t;

static log_watch_t g_log_watches[MAX_LOG_WATCHES];
static pthread_mutex_t g_log_lock = PTHREAD_MUTEX_INITIALIZER;

/* Base64编码表 */
static const char base64_table[] = 
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/* Base64编码 */
static char *base64_encode(const unsigned char *data, size_t input_len, size_t *output_len)
{
    *output_len = 4 * ((input_len + 2) / 3);
    char *encoded = malloc(*output_len + 1);
    if (!encoded) return NULL;
    
    size_t i, j;
    for (i = 0, j = 0; i < input_len;) {
        uint32_t octet_a = i < input_len ? data[i++] : 0;
        uint32_t octet_b = i < input_len ? data[i++] : 0;
        uint32_t octet_c = i < input_len ? data[i++] : 0;
        
        uint32_t triple = (octet_a << 16) + (octet_b << 8) + octet_c;
        
        encoded[j++] = base64_table[(triple >> 18) & 0x3F];
        encoded[j++] = base64_table[(triple >> 12) & 0x3F];
        encoded[j++] = base64_table[(triple >> 6) & 0x3F];
        encoded[j++] = base64_table[triple & 0x3F];
    }
    
    /* 添加padding */
    int mod = input_len % 3;
    if (mod > 0) {
        for (i = 0; i < (3 - mod); i++) {
            encoded[*output_len - 1 - i] = '=';
        }
    }
    
    encoded[*output_len] = '\0';
    return encoded;
}

/* 上传日志文件 */
int log_upload_file(agent_context_t *ctx, const char *filepath)
{
    if (!ctx || !filepath) return -1;
    
    FILE *fp = fopen(filepath, "rb");
    if (!fp) {
        LOG_ERROR("无法打开日志文件: %s", filepath);
        return -1;
    }
    
    /* 获取文件大小 */
    fseek(fp, 0, SEEK_END);
    long file_size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    LOG_INFO("上传日志文件: %s (大小: %ld bytes)", filepath, file_size);
    
    /* 分块上传 */
    unsigned char *buffer = malloc(LOG_CHUNK_SIZE);
    if (!buffer) {
        fclose(fp);
        return -1;
    }
    
    int chunk_num = 0;
    int total_chunks = (file_size + LOG_CHUNK_SIZE - 1) / LOG_CHUNK_SIZE;
    
    while (!feof(fp)) {
        size_t read_size = fread(buffer, 1, LOG_CHUNK_SIZE, fp);
        if (read_size == 0) break;
        
        /* Base64编码 */
        size_t encoded_len;
        char *encoded = base64_encode(buffer, read_size, &encoded_len);
        if (!encoded) continue;
        
        /* 构造JSON */
        char *json = malloc(encoded_len + 512);
        if (json) {
            snprintf(json, encoded_len + 512,
                "{"
                "\"filepath\":\"%s\","
                "\"chunk\":%d,"
                "\"total_chunks\":%d,"
                "\"size\":%zu,"
                "\"data\":\"%s\","
                "\"timestamp\":%" PRIu64 ""
                "}",
                filepath, chunk_num, total_chunks, read_size,
                encoded, get_timestamp_ms());
            
            socket_send_json(ctx, MSG_TYPE_LOG_UPLOAD, json);
            free(json);
        }
        
        free(encoded);
        chunk_num++;
        
        /* 避免发送过快 */
        usleep(10000);  /* 10ms */
    }
    
    free(buffer);
    fclose(fp);
    
    LOG_INFO("日志文件上传完成: %s (%d chunks)", filepath, chunk_num);
    return 0;
}

/* 获取文件末尾N行 */
int log_tail_file(agent_context_t *ctx, const char *filepath, int lines)
{
    if (!ctx || !filepath || lines <= 0) return -1;
    
    FILE *fp = fopen(filepath, "r");
    if (!fp) {
        LOG_ERROR("无法打开日志文件: %s", filepath);
        return -1;
    }
    
    /* 从文件末尾向前查找 */
    fseek(fp, 0, SEEK_END);
    long file_size = ftell(fp);
    
    if (file_size == 0) {
        fclose(fp);
        return 0;
    }
    
    /* 分配缓冲区存储结果 */
    char **line_ptrs = calloc(lines, sizeof(char *));
    
    /* 从末尾读取 */
    long pos = file_size - 1;
    char line_buf[4096];
    int line_pos = 0;
    int found_lines = 0;
    
    while (pos >= 0 && found_lines < lines) {
        fseek(fp, pos, SEEK_SET);
        int ch = fgetc(fp);
        
        if (ch == '\n' || pos == 0) {
            if (line_pos > 0 || pos == 0) {
                /* 反转行内容 */
                if (pos == 0 && ch != '\n') {
                    line_buf[line_pos++] = ch;
                }
                line_buf[line_pos] = '\0';
                
                /* 反转字符串 */
                for (int i = 0; i < line_pos / 2; i++) {
                    char tmp = line_buf[i];
                    line_buf[i] = line_buf[line_pos - 1 - i];
                    line_buf[line_pos - 1 - i] = tmp;
                }
                
                if (line_pos > 0) {
                    line_ptrs[found_lines] = strdup(line_buf);
                    found_lines++;
                }
                line_pos = 0;
            }
        } else {
            if (line_pos < sizeof(line_buf) - 1) {
                line_buf[line_pos++] = ch;
            }
        }
        pos--;
    }
    
    fclose(fp);
    
    /* 构造JSON并发送 */
    size_t json_size = found_lines * 4096 + 512;
    char *json = malloc(json_size);
    if (json) {
        int offset = snprintf(json, json_size,
            "{\"filepath\":\"%s\",\"lines\":%d,\"content\":[",
            filepath, found_lines);
        
        /* 反向输出行（因为是从末尾读取的） */
        for (int i = found_lines - 1; i >= 0; i--) {
            if (line_ptrs[i]) {
                /* 转义特殊字符 */
                offset += snprintf(json + offset, json_size - offset,
                    "%s\"%s\"", (i < found_lines - 1) ? "," : "", line_ptrs[i]);
            }
        }
        
        snprintf(json + offset, json_size - offset,
            "],\"timestamp\":%" PRIu64 "}", get_timestamp_ms());
        
        socket_send_json(ctx, MSG_TYPE_LOG_UPLOAD, json);
        free(json);
    }
    
    /* 释放内存 */
    for (int i = 0; i < found_lines; i++) {
        free(line_ptrs[i]);
    }
    free(line_ptrs);
    
    return 0;
}

/* 日志监控线程 */
static void *log_watch_thread(void *arg)
{
    log_watch_t *watch = (log_watch_t *)arg;
    
    LOG_INFO("开始监控日志: %s", watch->filepath);
    
    /* 打开文件并定位到末尾 */
    FILE *fp = fopen(watch->filepath, "r");
    if (!fp) {
        LOG_ERROR("无法打开监控文件: %s", watch->filepath);
        watch->active = false;
        return NULL;
    }
    
    fseek(fp, 0, SEEK_END);
    watch->last_pos = ftell(fp);
    
    char buffer[4096];
    
    while (watch->active && watch->ctx->running) {
        /* 检查文件是否有新内容 */
        fseek(fp, 0, SEEK_END);
        off_t current_pos = ftell(fp);
        
        if (current_pos > watch->last_pos) {
            /* 有新内容 */
            fseek(fp, watch->last_pos, SEEK_SET);
            
            while (fgets(buffer, sizeof(buffer), fp) != NULL) {
                /* 发送新日志行 */
                if (watch->ctx->connected && watch->ctx->authenticated) {
                    char *json = malloc(strlen(buffer) + 512);
                    if (json) {
                        /* 移除换行符 */
                        char *newline = strchr(buffer, '\n');
                        if (newline) *newline = '\0';
                        
                        snprintf(json, strlen(buffer) + 512,
                            "{\"filepath\":\"%s\",\"line\":\"%s\",\"timestamp\":%" PRIu64 "}",
                            watch->filepath, buffer, get_timestamp_ms());
                        
                        socket_send_json(watch->ctx, MSG_TYPE_LOG_UPLOAD, json);
                        free(json);
                    }
                }
            }
            
            watch->last_pos = ftell(fp);
        }
        
        /* 检查文件是否被截断或轮转 */
        struct stat st;
        if (stat(watch->filepath, &st) == 0) {
            if (st.st_size < watch->last_pos) {
                /* 文件被截断，重新定位 */
                LOG_INFO("日志文件被截断，重新开始监控: %s", watch->filepath);
                fclose(fp);
                fp = fopen(watch->filepath, "r");
                if (!fp) break;
                watch->last_pos = 0;
            }
        }
        
        usleep(500000);  /* 500ms */
    }
    
    if (fp) fclose(fp);
    watch->active = false;
    
    LOG_INFO("停止监控日志: %s", watch->filepath);
    return NULL;
}

/* 开始监控日志文件 */
int log_watch_start(agent_context_t *ctx, const char *filepath)
{
    if (!ctx || !filepath) return -1;
    
    pthread_mutex_lock(&g_log_lock);
    
    /* 查找空闲槽位 */
    int slot = -1;
    for (int i = 0; i < MAX_LOG_WATCHES; i++) {
        if (!g_log_watches[i].active) {
            slot = i;
            break;
        }
        /* 检查是否已经在监控 */
        if (strcmp(g_log_watches[i].filepath, filepath) == 0) {
            pthread_mutex_unlock(&g_log_lock);
            LOG_WARN("日志文件已在监控中: %s", filepath);
            return 0;
        }
    }
    
    if (slot < 0) {
        pthread_mutex_unlock(&g_log_lock);
        LOG_ERROR("日志监控槽位已满");
        return -1;
    }
    
    /* 初始化监控 */
    log_watch_t *watch = &g_log_watches[slot];
    memset(watch, 0, sizeof(log_watch_t));
    strncpy(watch->filepath, filepath, sizeof(watch->filepath) - 1);
    watch->ctx = ctx;
    watch->active = true;
    
    /* 启动监控线程 */
    if (pthread_create(&watch->thread, NULL, log_watch_thread, watch) != 0) {
        watch->active = false;
        pthread_mutex_unlock(&g_log_lock);
        LOG_ERROR("创建日志监控线程失败");
        return -1;
    }
    
    pthread_detach(watch->thread);
    
    pthread_mutex_unlock(&g_log_lock);
    
    LOG_INFO("开始监控日志: %s", filepath);
    return 0;
}

/* 停止监控日志文件 */
void log_watch_stop(agent_context_t *ctx, const char *filepath)
{
    pthread_mutex_lock(&g_log_lock);
    
    for (int i = 0; i < MAX_LOG_WATCHES; i++) {
        if (g_log_watches[i].active && 
            strcmp(g_log_watches[i].filepath, filepath) == 0) {
            g_log_watches[i].active = false;
            LOG_INFO("停止监控日志: %s", filepath);
            break;
        }
    }
    
    pthread_mutex_unlock(&g_log_lock);
}

/* 停止所有日志监控 */
void log_watch_stop_all(void)
{
    pthread_mutex_lock(&g_log_lock);
    
    for (int i = 0; i < MAX_LOG_WATCHES; i++) {
        g_log_watches[i].active = false;
    }
    
    pthread_mutex_unlock(&g_log_lock);
    
    /* 等待线程退出 */
    usleep(100000);
}

/* 读取文件内容（支持分块） */
int log_read_file(agent_context_t *ctx, const char *filepath, int offset, int length)
{
    if (!ctx || !filepath) return -1;
    
    LOG_INFO("[FILE_READ] 读取文件: %s, offset=%d, length=%d", filepath, offset, length);
    
    FILE *fp = fopen(filepath, "rb");
    if (!fp) {
        LOG_ERROR("[FILE_READ] 无法打开文件: %s", filepath);
        /* 返回错误消息 */
        char json[512];
        snprintf(json, sizeof(json), "{\"filepath\":\"%s\",\"error\":\"无法打开文件\"}", filepath);
        socket_send_json(ctx, MSG_TYPE_FILE_DATA, json);
        return -1;
    }
    
    fseek(fp, 0, SEEK_END);
    long file_size = ftell(fp);
    
    if (offset < 0) offset = 0;
    if (length <= 0 || length > 32768) length = 32768; /* 最大32KB，base64编码后约43KB，低于65534字节限制 */
    
    if (offset >= file_size) {
        fclose(fp);
        LOG_WARN("[FILE_READ] offset超出文件大小: offset=%d, file_size=%ld", offset, file_size);
        char json[512];
        snprintf(json, sizeof(json), "{\"filepath\":\"%s\",\"offset\":%d,\"length\":0,\"chunk_data\":\"\"}", filepath, offset);
        socket_send_json(ctx, MSG_TYPE_FILE_DATA, json);
        return 0;
    }
    
    fseek(fp, offset, SEEK_SET);
    
    int read_len = length;
    if (offset + read_len > file_size) {
        read_len = file_size - offset;
    }
    
    LOG_INFO("[FILE_READ] 准备读取 %d 字节 (offset=%d, file_size=%ld)", read_len, offset, file_size);
    
    unsigned char *buffer = malloc(read_len);
    if (!buffer) {
        fclose(fp);
        LOG_ERROR("[FILE_READ] 内存分配失败");
        return -1;
    }
    
    size_t actual_read = fread(buffer, 1, read_len, fp);
    fclose(fp);
    
    LOG_INFO("[FILE_READ] 实际读取 %zu 字节", actual_read);
    
    if (actual_read > 0) {
        size_t encoded_len;
        char *encoded = base64_encode(buffer, actual_read, &encoded_len);
        free(buffer);
        
        if (encoded) {
            LOG_INFO("[FILE_READ] base64编码后长度: %zu", encoded_len);
            size_t json_size = encoded_len + 1024;
            char *json = malloc(json_size);
            if (json) {
                snprintf(json, json_size,
                    "{\"filepath\":\"%s\",\"offset\":%d,\"length\":%zu,\"chunk_data\":\"%s\"}",
                    filepath, offset, actual_read, encoded);
                LOG_INFO("[FILE_READ] 发送文件数据: filepath=%s, offset=%d, length=%zu", filepath, offset, actual_read);
                socket_send_json(ctx, MSG_TYPE_FILE_DATA, json);
                free(json);
            } else {
                LOG_ERROR("[FILE_READ] JSON内存分配失败");
            }
            free(encoded);
        } else {
            LOG_ERROR("[FILE_READ] base64编码失败");
        }
    } else {
        LOG_WARN("[FILE_READ] 没有读取到任何数据");
    }
    
    return 0;
}

/* 列出可监控的日志文件 */
int log_list_files(agent_context_t *ctx, const char *log_dir)
{
    if (!ctx) return -1;
    
    const char *dir = log_dir ? log_dir : "/var/log";
    DIR *dp = opendir(dir);
    if (!dp) {
        LOG_ERROR("无法打开目录: %s", dir);
        return -1;
    }
    
    char json[8192];
    int offset = snprintf(json, sizeof(json), "{\"log_dir\":\"%s\",\"files\":[", dir);
    
    struct dirent *entry;
    int count = 0;
    
    while ((entry = readdir(dp)) != NULL) {
        if (entry->d_type == DT_REG) {  /* 只列出普通文件 */
            char filepath[512];
            snprintf(filepath, sizeof(filepath), "%s/%s", dir, entry->d_name);
            
            struct stat st;
            if (stat(filepath, &st) == 0) {
                offset += snprintf(json + offset, sizeof(json) - offset,
                    "%s{\"name\":\"%s\",\"size\":%ld}",
                    count > 0 ? "," : "", entry->d_name, (long)st.st_size);
                count++;
            }
        }
    }
    
    closedir(dp);
    
    snprintf(json + offset, sizeof(json) - offset, "]}");
    socket_send_json(ctx, MSG_TYPE_FILE_DATA, json);
    
    return 0;
}
