/*
 * 协议处理模块
 * 解析和处理WebSocket消息
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#include <time.h>
#include "agent.h"

/* 简单的本地 Base64 编码（用于小文件） */
static const char base64_table_local[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
static char *base64_encode_local(const unsigned char *data, size_t input_len, size_t *output_len)
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
        encoded[j++] = base64_table_local[(triple >> 18) & 0x3F];
        encoded[j++] = base64_table_local[(triple >> 12) & 0x3F];
        encoded[j++] = base64_table_local[(triple >> 6) & 0x3F];
        encoded[j++] = base64_table_local[triple & 0x3F];
    }
    int mod = input_len % 3;
    if (mod > 0) {
        for (i = 0; i < (3 - mod); i++) {
            encoded[*output_len - 1 - i] = '=';
        }
    }
    encoded[*output_len] = '\0';
    return encoded;
}

/* JSON字符串转义（处理特殊字符如、"\、/、\b、\f、\n、\r、\t） */
static char *json_escape_string(const char *src, size_t max_len)
{
    if (!src) return NULL;
    
    /* 预估输出大小（最坏情况每字符变成\uXXXX） */
    char *dst = malloc(max_len * 6 + 1);
    if (!dst) return NULL;
    
    size_t j = 0;
    for (size_t i = 0; src[i] && i < max_len && j < max_len * 6 - 10; i++) {
        unsigned char c = (unsigned char)src[i];
        
        switch (c) {
            case '"':
                dst[j++] = '\\';
                dst[j++] = '"';
                break;
            case '\\':
                dst[j++] = '\\';
                dst[j++] = '\\';
                break;
            case '\b':
                dst[j++] = '\\';
                dst[j++] = 'b';
                break;
            case '\f':
                dst[j++] = '\\';
                dst[j++] = 'f';
                break;
            case '\n':
                dst[j++] = '\\';
                dst[j++] = 'n';
                break;
            case '\r':
                dst[j++] = '\\';
                dst[j++] = 'r';
                break;
            case '\t':
                dst[j++] = '\\';
                dst[j++] = 't';
                break;
            default:
                if (c < 0x20 || c >= 0x7F) {
                    /* 控制字符或非ASCII用\uXXXX表示 */
                    j += snprintf(dst + j, max_len * 6 - j, "\\u%04x", c);
                } else {
                    dst[j++] = c;
                }
                break;
        }
    }
    
    dst[j] = '\0';
    return dst;
}

/* 简单的JSON解析辅助函数 */
static char *json_get_string(const char *json, const char *key)
{
    char search[128];
    snprintf(search, sizeof(search), "\"%s\":", key);
    
    char *pos = strstr(json, search);
    if (!pos) return NULL;
    
    pos += strlen(search);
    while (*pos && isspace(*pos)) pos++;
    
    if (*pos != '"') return NULL;
    pos++;
    
    char *end = strchr(pos, '"');
    if (!end) return NULL;
    
    size_t len = end - pos;
    char *result = malloc(len + 1);
    if (!result) return NULL;
    
    memcpy(result, pos, len);
    result[len] = '\0';
    
    return result;
}

static int json_get_int(const char *json, const char *key, int default_val)
{
    char search[128];
    snprintf(search, sizeof(search), "\"%s\":", key);
    
    char *pos = strstr(json, search);
    if (!pos) return default_val;
    
    pos += strlen(search);
    while (*pos && isspace(*pos)) pos++;
    
    return atoi(pos);
}

static bool json_get_bool(const char *json, const char *key, bool default_val)
{
    char search[128];
    snprintf(search, sizeof(search), "\"%s\":", key);
    
    char *pos = strstr(json, search);
    if (!pos) return default_val;
    
    pos += strlen(search);
    while (*pos && isspace(*pos)) pos++;
    
    if (strncmp(pos, "true", 4) == 0) return true;
    if (strncmp(pos, "false", 5) == 0) return false;
    
    return default_val;
}

/* 处理认证结果 */
static void handle_auth_result(agent_context_t *ctx, const char *data)
{
    bool success = json_get_bool(data, "success", false);
    char *message = json_get_string(data, "message");
    
    if (success) {
        ctx->authenticated = true;
        LOG_INFO("认证成功: %s", message ? message : "");
    } else {
        ctx->authenticated = false;
        LOG_ERROR("认证失败: %s", message ? message : "unknown");
    }
    
    if (message) free(message);
}

/* 处理脚本接收 */
static void handle_script_recv(agent_context_t *ctx, const char *data)
{
    char *script_id = json_get_string(data, "script_id");
    char *content = json_get_string(data, "content");
    char *filename = json_get_string(data, "filename");
    bool execute = json_get_bool(data, "execute", true);
    
    if (!script_id) {
        LOG_ERROR("脚本消息缺少script_id");
        goto cleanup;
    }
    
    if (content) {
        /* 内联脚本 */
        if (execute) {
            script_execute_inline(ctx, script_id, content);
        } else {
            /* 只保存不执行 */
            char path[512];
            snprintf(path, sizeof(path), "%s/%s", 
                     ctx->config.script_path, 
                     filename ? filename : script_id);
            script_save(script_id, content, path);
        }
    } else if (filename) {
        /* 执行已保存的脚本 */
        char path[512];
        snprintf(path, sizeof(path), "%s/%s", ctx->config.script_path, filename);
        script_execute(ctx, script_id, path);
    }
    
cleanup:
    if (script_id) free(script_id);
    if (content) free(content);
    if (filename) free(filename);
}

/* 处理PTY创建请求 */
static void handle_pty_create(agent_context_t *ctx, const char *data)
{
    int session_id = json_get_int(data, "session_id", -1);
    int rows = json_get_int(data, "rows", 24);
    int cols = json_get_int(data, "cols", 80);
    
    if (session_id < 0) {
        LOG_ERROR("PTY创建请求缺少session_id");
        return;
    }
    
    pty_create_session(ctx, session_id, rows, cols);
}

/* 处理PTY数据 */
static void handle_pty_data(agent_context_t *ctx, const char *data)
{
    int session_id = json_get_int(data, "session_id", -1);
    char *pty_data = json_get_string(data, "data");
    
    if (session_id < 0 || !pty_data) {
        if (pty_data) free(pty_data);
        return;
    }
    LOG_INFO("收到 PTY_DATA 要写入: session_id=%d, data_len=%zu", session_id, strlen(pty_data));
    pty_write_data(ctx, session_id, pty_data, strlen(pty_data));
    free(pty_data);
}

/* 处理PTY窗口大小调整 */
static void handle_pty_resize(agent_context_t *ctx, const char *data)
{
    int session_id = json_get_int(data, "session_id", -1);
    int rows = json_get_int(data, "rows", 24);
    int cols = json_get_int(data, "cols", 80);
    
    if (session_id >= 0) {
        pty_resize(ctx, session_id, rows, cols);
    }
}

/* 处理PTY关闭 */
static void handle_pty_close(agent_context_t *ctx, const char *data)
{
    int session_id = json_get_int(data, "session_id", -1);
    
    if (session_id >= 0) {
        pty_close_session(ctx, session_id);
    }
}

/* 处理文件请求 */
static void handle_file_request(agent_context_t *ctx, const char *data)
{
    char *action = json_get_string(data, "action");
    char *filepath = json_get_string(data, "filepath");
    int lines = json_get_int(data, "lines", 100);
    
    if (!action) {
        goto cleanup;
    }
    
    if (strcmp(action, "upload") == 0 && filepath) {
        log_upload_file(ctx, filepath);
    } else if (strcmp(action, "tail") == 0 && filepath) {
        log_tail_file(ctx, filepath, lines);
    } else if (strcmp(action, "watch") == 0 && filepath) {
        log_watch_start(ctx, filepath);
    } else if (strcmp(action, "unwatch") == 0 && filepath) {
        log_watch_stop(ctx, filepath);
    } else if (strcmp(action, "list") == 0) {
        log_list_files(ctx, filepath);
    }
    
cleanup:
    if (action) free(action);
    if (filepath) free(filepath);
}

/* 文件信息结构体 */
typedef struct {
    char name[512];
    char path[2048];
    int is_dir;
    long size;
} file_entry_t;

/* 现代风格排序比较函数：文件夹优先，然后按名字不区分大小写排序 */
static int compare_files(const void *a, const void *b)
{
    const file_entry_t *fa = (const file_entry_t *)a;
    const file_entry_t *fb = (const file_entry_t *)b;
    
    /* 文件夹优先 */
    if (fa->is_dir != fb->is_dir) {
        return fb->is_dir - fa->is_dir;  /* 文件夹返回结果为1，文件为-1 */
    }
    
    /* 同类型按名字不区分大小写排序 */
    return strcasecmp(fa->name, fb->name);
}

/* 规范化路径：确保以/ 开头，不重复/ */
static void normalize_path(const char *src, char *dst, size_t dstlen)
{
    if (!src || dstlen < 2) {
        if (dstlen > 0) {
            dst[0] = '/';
            dst[1] = '\0';
        }
        return;
    }
    
    int i = 0, j = 0;
    
    /* 处理空字符串 */
    if (src[0] == '\0') {
        dst[0] = '/';
        dst[1] = '\0';
        return;
    }
    
    /* 确保以/ 开头 */
    if (src[0] != '/') {
        if (j < (int)dstlen - 1) dst[j++] = '/';
    }
    
    for (i = 0; src[i] && j < (int)dstlen - 1; i++) {
        /* 过滤连续的/ */
        if (src[i] == '/' && j > 0 && dst[j-1] == '/') {
            continue;
        }
        dst[j++] = src[i];
    }
    
    /* 移除末尾的/ (如果不是根目录) */
    if (j > 1 && dst[j-1] == '/') {
        j--;
    }
    
    dst[j] = '\0';
}

/* 处理文件列表请求（通用目录列表） */
static void handle_file_list_request(agent_context_t *ctx, const char *data)
{
    char *path = json_get_string(data, "path");
    char *request_id = json_get_string(data, "request_id");

    char normalized_dir[2048];
    normalize_path(path, normalized_dir, sizeof(normalized_dir));
    
    const char *dir = normalized_dir;
    DIR *dp = opendir(dir);
    if (!dp) {
        LOG_ERROR("无法打开目录: %s", dir);
        /* 返回空响应 */
        char json[512];
        if (request_id) {
            snprintf(json, sizeof(json), "{\"path\":\"%s\",\"files\":[],\"request_id\":\"%s\"}", dir, request_id);
        } else {
            snprintf(json, sizeof(json), "{\"path\":\"%s\",\"files\":[]}", dir);
        }
        ws_send_json(ctx, MSG_TYPE_FILE_LIST_RESPONSE, json);
        if (path) free(path);
        if (request_id) free(request_id);
        return;
    }

    /* 收集目录项到数组 */
    file_entry_t *entries = malloc(sizeof(file_entry_t) * 1024);
    if (!entries) {
        LOG_ERROR("内存不足");
        closedir(dp);
        goto cleanup;
    }

    struct dirent *entry;
    int count = 0;
    struct stat st;
    char filepath[2048];

    while ((entry = readdir(dp)) != NULL && count < 1024) {
        /* 跳过. 和 .. */
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) {
            continue;
        }
        
        /* 构造完整路径 */
        if (strcmp(dir, "/") == 0) {
            snprintf(filepath, sizeof(filepath), "/%s", entry->d_name);
        } else {
            snprintf(filepath, sizeof(filepath), "%s/%s", dir, entry->d_name);
        }
        
        if (stat(filepath, &st) == 0) {
            file_entry_t *e = &entries[count];
            strncpy(e->name, entry->d_name, sizeof(e->name) - 1);
            e->name[sizeof(e->name) - 1] = '\0';
            strncpy(e->path, filepath, sizeof(e->path) - 1);
            e->path[sizeof(e->path) - 1] = '\0';
            e->is_dir = S_ISDIR(st.st_mode) ? 1 : 0;
            e->size = st.st_size;
            count++;
        }
    }

    closedir(dp);

    /* 排序 */
    qsort(entries, count, sizeof(file_entry_t), compare_files);

    /* 动态构造JSON响应（避免缓冲区溢出） */
    char *json = malloc(131072);  /* 128KB缓冲 */
    if (!json) {
        LOG_ERROR("内存不足");
        free(entries);
        goto cleanup;
    }
    
    int offset = snprintf(json, 131072, "{\"path\":\"%s\",\"files\":[", dir);
    
    for (int i = 0; i < count && offset < 131072 - 1024; i++) {
        char *esc_name = json_escape_string(entries[i].name, sizeof(entries[i].name));
        char *esc_path = json_escape_string(entries[i].path, sizeof(entries[i].path));
        
        if (esc_name && esc_path) {
            offset += snprintf(json + offset, 131072 - offset,
                "%s{\"name\":\"%s\",\"path\":\"%s\",\"is_dir\":%d,\"size\":%lld}",
                i > 0 ? "," : "", esc_name, esc_path, entries[i].is_dir, (long long)entries[i].size);
        }
        
        if (esc_name) free(esc_name);
        if (esc_path) free(esc_path);
    }

    offset += snprintf(json + offset, 131072 - offset, "]");
    if (request_id) {
        offset += snprintf(json + offset, 131072 - offset, ",\"request_id\":\"%s\"", request_id);
    }
    snprintf(json + offset, 131072 - offset, "}");

    ws_send_json(ctx, MSG_TYPE_FILE_LIST_RESPONSE, json);

    free(json);
    free(entries);

cleanup:
    if (path) free(path);
    if (request_id) free(request_id);
}

/* 处理打包并发送请求 */
static void handle_download_package(agent_context_t *ctx, const char *data)
{
    char *path = json_get_string(data, "path");
    char *format = json_get_string(data, "format");
    char *request_id = json_get_string(data, "request_id");

    if (!path) {
        LOG_ERROR("打包请求: 缺少path参数");
        goto cleanup;
    }
    
    LOG_INFO("打包请求 [%s]: path=%s, format=%s", request_id ? request_id : "unknown", path, format ? format : "zip");

    /* 规范化路径 */
    char normalized_check[2048];
    normalize_path(path, normalized_check, sizeof(normalized_check));
    
    /* 检查文件/目录是否存在 */
    struct stat st;
    if (stat(normalized_check, &st) != 0) {
        LOG_ERROR("路径不存在: %s", normalized_check);
        goto cleanup;
    }

    /* 提取相对路径进行压缩（去掉前导/) */
    const char *rel_path = normalized_check;
    if (rel_path[0] == '/' && rel_path[1] != '\0') {
        rel_path = normalized_check + 1;
    }

    /* 生成临时归档文件 */
    char tmpfile[256];
    snprintf(tmpfile, sizeof(tmpfile), "/tmp/agent_pkg_%d_%llu", getpid(), (unsigned long long)get_timestamp_ms());
    char archive[320];
    int ret = -1;
    
    if (format && strcmp(format, "tar.gz") == 0) {
        snprintf(archive, sizeof(archive), "%s.tar.gz", tmpfile);
        char cmd[1024];
        snprintf(cmd, sizeof(cmd), "tar -czf '%s' -C / '%s' 2>&1", archive, rel_path);
        LOG_DEBUG("执行压缩: %s", cmd);
        ret = system(cmd);
        if (ret != 0) {
            LOG_ERROR("tar命令失败: ret=%d, errno=%d", ret, errno);
        } else {
            LOG_INFO("tar压缩完成");
        }
    } else {
        snprintf(archive, sizeof(archive), "%s.zip", tmpfile);
        char cmd[1024];
        snprintf(cmd, sizeof(cmd), "cd / && zip -rq '%s' '%s' 2>&1", archive, rel_path);
        LOG_DEBUG("执行压缩: %s", cmd);
        ret = system(cmd);
        if (ret != 0) {
            LOG_ERROR("zip命令失败: ret=%d, errno=%d", ret, errno);
        } else {
            LOG_INFO("zip压缩完成");
        }
    }

    /* 读取文件并base64编码后发送 */
    FILE *fp = fopen(archive, "rb");
    if (!fp) {
        LOG_ERROR("无法打开归档: %s (可能压缩失败)", archive);
        goto cleanup;
    }
    fseek(fp, 0, SEEK_END);
    long fsize = ftell(fp);
    fseek(fp, 0, SEEK_SET);

    LOG_INFO("归档文件大小: %ld bytes", fsize);
    
    #define MAX_DOWNLOAD_SIZE  (50 * 1024 * 1024)  /* 50MB */
    if (fsize <= 0 || fsize > MAX_DOWNLOAD_SIZE) {
        LOG_ERROR("归档大小不合适: %ld (限制:%d MB)", fsize, MAX_DOWNLOAD_SIZE / (1024 * 1024));
        fclose(fp);
        unlink(archive);
        goto cleanup;
    }

    unsigned char *buf = malloc(fsize);
    if (!buf) {
        LOG_ERROR("内存分配失败: %ld bytes", fsize);
        fclose(fp);
        unlink(archive);
        goto cleanup;
    }
    size_t read_size = fread(buf, 1, fsize, fp);
    fclose(fp);
    
    if (read_size != (size_t)fsize) {
        LOG_ERROR("读取文件失败: 期望%ld, 实际%zu", fsize, read_size);
        free(buf);
        unlink(archive);
        goto cleanup;
    }

    size_t encoded_len;
    char *encoded = base64_encode_local(buf, fsize, &encoded_len);
    free(buf);

    if (encoded) {
        /* 安全构建JSON（转义文件名） */
        const char *filename = strrchr(archive, '/') ? strrchr(archive, '/') + 1 : archive;
        char *esc_filename = json_escape_string(filename, strlen(filename));
        
        size_t json_size = encoded_len + 1024;
        char *json = malloc(json_size);
        if (json && esc_filename) {
            int offset = 0;
            offset += snprintf(json + offset, json_size - offset,
                "{\"filename\":\"%s\",\"size\":%lld,\"content\":\"", esc_filename, (long long)fsize);
            offset += snprintf(json + offset, json_size - offset, "%s", encoded);
            offset += snprintf(json + offset, json_size - offset, "\"");
            if (request_id) {
                offset += snprintf(json + offset, json_size - offset, ",\"request_id\":\"%s\"", request_id);
            }
            snprintf(json + offset, json_size - offset, "}");
            
            LOG_INFO("发送打包响应: 文件=%s, 大小=%lld, 编码后=%zu", filename, (long long)fsize, encoded_len);
            ws_send_json(ctx, MSG_TYPE_DOWNLOAD_PACKAGE, json);
            free(json);
        } else {
            LOG_ERROR("JSON缓冲区或转义分配失败");
        }
        if (esc_filename) free(esc_filename);
        free(encoded);
    } else {
        LOG_ERROR("base64编码失败");
    }

    /* 清理临时文件 */
    if (unlink(archive) == 0) {
        LOG_DEBUG("删除临时文件: %s", archive);
    }

cleanup:
    if (path) free(path);
    if (format) free(format);
    if (request_id) free(request_id);
}

/* 处理命令请求 */
static void handle_cmd_request(agent_context_t *ctx, const char *data)
{
    char *cmd = json_get_string(data, "cmd");
    char *request_id = json_get_string(data, "request_id");
    
    if (!cmd) {
        goto cleanup;
    }
    
    /* 内置命令处理 */
    if (strcmp(cmd, "status") == 0) {
        /* 立即上报状态 */
        system_status_t status;
        status_collect(&status);
        char *json = status_to_json(&status);
        if (json) {
            ws_send_json(ctx, MSG_TYPE_SYSTEM_STATUS, json);
            free(json);
        }
    } else if (strcmp(cmd, "reboot") == 0) {
        LOG_WARN("收到重启命令");
        system("reboot");
    } else if (strcmp(cmd, "pty_list") == 0) {
        pty_list_sessions(ctx);
    } else if (strcmp(cmd, "script_list") == 0) {
        script_list(ctx);
    } else {
        /* 执行shell命令 */
        script_execute_inline(ctx, request_id ? request_id : "cmd", cmd);
    }
    
cleanup:
    if (cmd) free(cmd);
    if (request_id) free(request_id);
}

/* 处理消息 */
int protocol_handle_message(agent_context_t *ctx, const char *data, size_t len)
{
    if (!ctx || !data || len < 1) return -1;
    
    /* 消息格式: 类型(1字节) + JSON数据 */
    msg_type_t type = (msg_type_t)(unsigned char)data[0];
    const char *json_data = data + 1;
    
    LOG_DEBUG("收到消息: type=0x%02X, len=%zu", (unsigned char)type, len);
    
    switch (type) {
    case MSG_TYPE_AUTH_RESULT:
        handle_auth_result(ctx, json_data);
        break;
        
    case MSG_TYPE_SCRIPT_RECV:
        handle_script_recv(ctx, json_data);
        break;
        
    case MSG_TYPE_PTY_CREATE:
        handle_pty_create(ctx, json_data);
        break;
        
    case MSG_TYPE_PTY_DATA:
        handle_pty_data(ctx, json_data);
        break;
        
    case MSG_TYPE_PTY_RESIZE:
        handle_pty_resize(ctx, json_data);
        break;
        
    case MSG_TYPE_PTY_CLOSE:
        handle_pty_close(ctx, json_data);
        break;
        
    case MSG_TYPE_FILE_REQUEST:
        handle_file_request(ctx, json_data);
        break;
    case MSG_TYPE_FILE_LIST_REQUEST:
        handle_file_list_request(ctx, json_data);
        break;
    case MSG_TYPE_DOWNLOAD_PACKAGE:
        handle_download_package(ctx, json_data);
        break;
        
    case MSG_TYPE_CMD_REQUEST:
        handle_cmd_request(ctx, json_data);
        break;
        
    case MSG_TYPE_HEARTBEAT:
        /* 心跳响应 */
        LOG_DEBUG("收到心跳响应");
        break;

    case MSG_TYPE_DEVICE_LIST:
        /* 设备列表更新（来自服务器） */
        LOG_INFO("收到设备列表更新: %s", json_data);
        break;
        
    default:
        LOG_WARN("未知消息类型: 0x%02X", type);
        break;
    }
    
    return 0;
}

/* 创建认证消息 */
char *protocol_create_auth_msg(agent_context_t *ctx)
{
    if (!ctx) return NULL;
    
    char *json = malloc(512);
    if (!json) return NULL;
    
    snprintf(json, 512,
        "{"
        "\"device_id\":\"%s\","
        "\"token\":\"%s\","
        "\"version\":\"%s\","
        "\"timestamp\":%" PRIu64 ""
        "}",
        ctx->config.device_id,
        ctx->config.auth_token,
        AGENT_VERSION,
        get_timestamp_ms());
    
    return json;
}

/* 创建心跳消息 */
char *protocol_create_heartbeat(agent_context_t *ctx)
{
    if (!ctx) return NULL;
    
    char *json = malloc(256);
    if (!json) return NULL;
    
    snprintf(json, 256,
        "{\"timestamp\":%" PRIu64 ",\"uptime\":%u}",
        get_timestamp_ms(),
        (unsigned int)(time(NULL)));  /* 简单起见用当前时间 */
    
    return json;
}
