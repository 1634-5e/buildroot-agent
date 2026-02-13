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
                if (c < 0x20 || c >= 0x80) {
                    /* 控制字符和非ASCII用\uXXXX表示 */
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
char *json_get_string(const char *json, const char *key)
{
    char search[128];
    snprintf(search, sizeof(search), "\"%s\"", key);
    
    char *pos = strstr(json, search);
    if (!pos) return NULL;
    
    pos += strlen(search);
    while (*pos && isspace(*pos)) pos++;
    
    if (*pos != ':') return NULL;
    pos++;
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

/* Shell argument escaping to prevent command injection */
static void escape_shell_arg(const char *src, char *dst, size_t dst_size) {
    if (!src || !dst || dst_size == 0) return;
    
    if (dst_size < 3) {
        dst[0] = '\0';
        return;
    }
    
    size_t src_len = strlen(src);
    size_t dst_idx = 0;
    
    // Simple approach: wrap in single quotes and handle single quotes inside
    dst[dst_idx++] = '\'';
    
    for (size_t i = 0; i < src_len && dst_idx < dst_size - 3; i++) {
        if (src[i] == '\'') {
            // Close the quote, add escaped quote, start new quote
            dst[dst_idx++] = '\'';
            if (dst_idx < dst_size - 3) dst[dst_idx++] = '\\';
            if (dst_idx < dst_size - 3) dst[dst_idx++] = '\'';
            if (dst_idx < dst_size - 3) dst[dst_idx++] = '\'';
        } else {
            dst[dst_idx++] = src[i];
        }
    }
    
    if (dst_idx < dst_size - 1) {
        dst[dst_idx++] = '\'';
    }
    dst[dst_idx] = '\0';
}

/* Parse a JSON array of strings into a dynamically allocated array */
static char **parse_json_string_array(const char *json, const char *key, int *count) {
    char search[128];
    snprintf(search, sizeof(search), "\"%s\":", key);
    
    char *pos = strstr(json, search);
    if (!pos) {
        *count = 0;
        return NULL;
    }
    
    pos += strlen(search);
    while (*pos && isspace(*pos)) pos++;
    
    if (*pos != '[') {
        *count = 0;
        return NULL;
    }
    pos++; // Skip '['
    
    // First pass: count the number of strings
    int string_count = 0;
    char *parse_pos = pos;
    
    while (*parse_pos && *parse_pos != ']') {
        // Skip whitespace
        while (*parse_pos && isspace(*parse_pos)) parse_pos++;
        
        if (*parse_pos == '"') {
            string_count++;
            parse_pos++; // Skip opening quote
            
            // Find closing quote
            while (*parse_pos && *parse_pos != '"') {
                if (*parse_pos == '\\' && *(parse_pos + 1)) {
                    parse_pos += 2; // Skip escaped character
                } else {
                    parse_pos++;
                }
            }
            if (*parse_pos == '"') parse_pos++;
        }
        
        // Skip to next element (comma or closing bracket)
        while (*parse_pos && *parse_pos != ',' && *parse_pos != ']') parse_pos++;
        if (*parse_pos == ',') parse_pos++;
    }
    
    if (string_count == 0) {
        *count = 0;
        return NULL;
    }
    
    // Allocate array for string pointers
    char **result = malloc(sizeof(char*) * string_count);
    if (!result) {
        *count = 0;
        return NULL;
    }
    
    // Reset and parse the strings
    parse_pos = pos;
    int index = 0;
    
    while (*parse_pos && index < string_count && *parse_pos != ']') {
        // Skip whitespace
        while (*parse_pos && isspace(*parse_pos)) parse_pos++;
        
        if (*parse_pos == '"') {
            parse_pos++; // Skip opening quote
            char *start = parse_pos;
            size_t len = 0;
            
            // Find closing quote
            while (*parse_pos && *parse_pos != '"') {
                if (*parse_pos == '\\' && *(parse_pos + 1)) {
                    len++;
                    parse_pos += 2; // Skip escaped character
                } else {
                    len++;
                    parse_pos++;
                }
            }
            
            // Allocate and copy string, handling escaped characters
            char *str = malloc(len + 1);
            if (str) {
                char *dst = str;
                parse_pos = start;
                
                while (*parse_pos && *parse_pos != '"') {
                    if (*parse_pos == '\\' && *(parse_pos + 1)) {
                        char next = *(parse_pos + 1);
                        switch (next) {
                            case 'n': *dst++ = '\n'; break;
                            case 'r': *dst++ = '\r'; break;
                            case 't': *dst++ = '\t'; break;
                            case 'b': *dst++ = '\b'; break;
                            case 'f': *dst++ = '\f'; break;
                            case '\\': *dst++ = '\\'; break;
                            case '"': *dst++ = '"'; break;
                            default: *dst++ = next; break;
                        }
                        parse_pos += 2;
                    } else {
                        *dst++ = *parse_pos++;
                    }
                }
                *dst = '\0';
                result[index++] = str;
            }
            
            if (*parse_pos == '"') parse_pos++;
        }
        
        // Skip to next element (comma or closing bracket)
        while (*parse_pos && *parse_pos != ',' && *parse_pos != ']') parse_pos++;
        if (*parse_pos == ',') parse_pos++;
    }
    
    *count = index;
    return result;
}

/* Free the string array allocated by parse_json_string_array */
static void free_string_array(char **array, int count) {
    if (!array) return;
    
    for (int i = 0; i < count; i++) {
        if (array[i]) {
            free(array[i]);
        }
    }
    free(array);
}

int json_get_int(const char *json, const char *key, int default_val)
{
    char search[128];
    snprintf(search, sizeof(search), "\"%s\":", key);
    
    char *pos = strstr(json, search);
    if (!pos) return default_val;
    
    pos += strlen(search);
    while (*pos && isspace(*pos)) pos++;
    
    return atoi(pos);
}

int64_t json_get_int64(const char *json, const char *key)
{
    char search[128];
    snprintf(search, sizeof(search), "\"%s\":", key);
    
    char *pos = strstr(json, search);
    if (!pos) return 0;
    
    pos += strlen(search);
    while (*pos && isspace(*pos)) pos++;
    
    return atoll(pos);
}

bool json_get_bool(const char *json, const char *key, bool default_val)
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
    LOG_DEBUG("收到认证响应JSON: %s", data ? data : "null");

    bool success = json_get_bool(data, "success", false);
    char *message = json_get_string(data, "message");

    LOG_DEBUG("解析认证结果: success=%d, message=%s", success, message ? message : "null");

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
    /* 支持 sessionId (驼峰) 和 session_id (下划线) 两种命名 */
    int session_id = json_get_int(data, "sessionId", -1);
    if (session_id < 0) {
        session_id = json_get_int(data, "session_id", -1);
    }
    int rows = json_get_int(data, "rows", 24);
    int cols = json_get_int(data, "cols", 80);

    if (session_id < 0) {
        LOG_ERROR("PTY创建请求缺少session_id或sessionId");
        return;
    }

    pty_create_session(ctx, session_id, rows, cols);
}

/* 处理PTY数据 */
static void handle_pty_data(agent_context_t *ctx, const char *data)
{
    /* 支持 sessionId (驼峰) 和 session_id (下划线) 两种命名 */
    int session_id = json_get_int(data, "sessionId", -1);
    if (session_id < 0) {
        session_id = json_get_int(data, "session_id", -1);
    }
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
    /* 支持 sessionId (驼峰) 和 session_id (下划线) 两种命名 */
    int session_id = json_get_int(data, "sessionId", -1);
    if (session_id < 0) {
        session_id = json_get_int(data, "session_id", -1);
    }
    int rows = json_get_int(data, "rows", 24);
    int cols = json_get_int(data, "cols", 80);

    if (session_id >= 0) {
        pty_resize(ctx, session_id, rows, cols);
    }
}

/* 处理PTY关闭 */
static void handle_pty_close(agent_context_t *ctx, const char *data)
{
    /* 支持 sessionId (驼峰) 和 session_id (下划线) 两种命名 */
    int session_id = json_get_int(data, "sessionId", -1);
    if (session_id < 0) {
        session_id = json_get_int(data, "session_id", -1);
    }

    if (session_id >= 0) {
        pty_close_session(ctx, session_id);
    }
}

/* 处理文件请求 */
static void handle_file_request(agent_context_t *ctx, const char *data)
{
    LOG_INFO("[FILE_REQUEST] Received file request, data: %s", data);
    
    char *action = json_get_string(data, "action");
    char *filepath = json_get_string(data, "filepath");
    int lines = json_get_int(data, "lines", 100);
    int offset = json_get_int(data, "offset", 0);
    int length = json_get_int(data, "length", 0);
    
    LOG_INFO("[FILE_REQUEST] Parsed: action=%s, filepath=%s, offset=%d, length=%d",
             action ? action : "null", filepath ? filepath : "null", offset, length);
    
    if (!action) {
        LOG_ERROR("[FILE_REQUEST] No action specified");
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
    } else if (strcmp(action, "read") == 0 && filepath) {
        LOG_INFO("[FILE_REQUEST] Calling log_read_file for %s", filepath);
        log_read_file(ctx, filepath, offset, length);
    } else {
        LOG_WARN("[FILE_REQUEST] Unknown action: %s", action);
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

    char default_request_id[64];
    if (!request_id) {
        snprintf(default_request_id, sizeof(default_request_id), "req-%lld", (long long)get_timestamp_ms());
        request_id = default_request_id;
        LOG_INFO("未提供request_id, 使用默认值: %s", request_id);
    }

    LOG_INFO("文件列表请求: 原始路径='%s' (规范化后='%s'), request_id='%s'", path ? path : "null", dir, request_id);

    DIR *dp = opendir(dir);
    if (!dp) {
        LOG_ERROR("无法打开目录: %s (errno=%d: %s)", dir, errno, strerror(errno));
        /* 返回空响应 */
        char json[512];
        snprintf(json, sizeof(json), "{\"path\":\"%s\",\"files\":[],\"request_id\":\"%s\"}", dir, request_id);
        socket_send_json(ctx, MSG_TYPE_FILE_LIST_RESPONSE, json);
        if (path) free(path);
        if (request_id != default_request_id) free(request_id);
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
        /* 跳过 . 和 .. */
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

    LOG_INFO("找到 %d 个文件/目录 (在目录: %s)", count, dir);

    /* 排序 */
    qsort(entries, count, sizeof(file_entry_t), compare_files);

    /* 分块发送JSON响应（避免单条消息过大） */
    /* WebSocket消息大小限制为65534字节，每个文件约需要200-300字节，所以每个chunk最多20-30个文件 */
    const int CHUNK_SIZE = 20; /* 每个chunk最多20个文件 */
    int chunk_num = 0;
    int total_chunks = (count + CHUNK_SIZE - 1) / CHUNK_SIZE;
    
    LOG_INFO("将分 %d 个chunk发送, 每个chunk最多 %d 个文件 (总数: %d)", total_chunks, CHUNK_SIZE, count);
    
    for (int i = 0; i < count; i += CHUNK_SIZE) {
        int chunk_end = (i + CHUNK_SIZE < count) ? (i + CHUNK_SIZE) : count;
        int files_in_chunk = chunk_end - i;
        
        /* 使用较小缓冲区（128KB），确保不会超过WebSocket限制 */
        const int JSON_BUF_SIZE = 131072;
        char *json = malloc(JSON_BUF_SIZE);
        if (!json) {
            LOG_ERROR("内存不足");
            free(entries);
            goto cleanup;
        }
        
         /* 估算剩余空间（需要为JSON头部和尾部预留空间） */
        const int reserved_space = 512;
        int available_space = JSON_BUF_SIZE - reserved_space;

        LOG_INFO("准备发送chunk %d/%d，请求路径='%s'，dir='%s'，文件数=%d",
                  chunk_num, total_chunks, path, dir, files_in_chunk);

        int offset = snprintf(json, JSON_BUF_SIZE, "{\"path\":\"%s\",\"files\":[", dir);

        /* 遍历这个chunk的所有文件 */
        int files_added = 0;
        for (int j = i; j < chunk_end && offset < available_space; j++) {
            char *esc_name = json_escape_string(entries[j].name, sizeof(entries[j].name));
            char *esc_path = json_escape_string(entries[j].path, sizeof(entries[j].path));
            
            LOG_INFO("  文件[%d]: name='%s', path='%s'",
                     j, entries[j].name, entries[j].path);
            
            if (esc_name && esc_path) {
                int len = snprintf(json + offset, JSON_BUF_SIZE - offset,
                    "%s{\"name\":\"%s\",\"path\":\"%s\",\"is_dir\":%d,\"size\":%lld}",
                    (j > i) ? "," : "", esc_name, esc_path, entries[j].is_dir, (long long)entries[j].size);

                /* 检查是否有足够的剩余空间 */
                if (offset + len < available_space) {
                    offset += len;
                    files_added++;
                } else {
                    /* 空间不足，停止添加 */
                    LOG_WARN("Chunk %d 空间不足，只添加了 %d/%d 个文件 (offset=%d, space=%d)",
                             chunk_num, files_added, files_in_chunk, offset, available_space);
                    if (esc_name) free(esc_name);
                    if (esc_path) free(esc_path);
                    break;
                }
            }

            if (esc_name) free(esc_name);
            if (esc_path) free(esc_path);
        }

        /* 添加元数据 */
        offset += snprintf(json + offset, JSON_BUF_SIZE - offset, "]");
        offset += snprintf(json + offset, JSON_BUF_SIZE - offset, ",\"chunk\":%d,\"total_chunks\":%d", chunk_num, total_chunks);
        offset += snprintf(json + offset, JSON_BUF_SIZE - offset, ",\"request_id\":\"%s\"", request_id);
        snprintf(json + offset, JSON_BUF_SIZE - offset, "}");

        /* 检查最终消息大小是否超过限制 */
        if (offset > 65534) {
            LOG_ERROR("消息太大: %d > 65534，发送失败", offset);
            free(json);
            free(entries);
            goto cleanup;
        }

        LOG_INFO("发送chunk %d/%d, 文件数: %d/%d, 消息大小: %d字节", 
                 chunk_num, total_chunks, files_added, files_in_chunk, offset);
        int rc = socket_send_json(ctx, MSG_TYPE_FILE_LIST_RESPONSE, json);
        if (rc != 0) {
            LOG_ERROR("发送chunk %d 失败: %d", chunk_num, rc);
        }
        free(json);
        
        chunk_num++;
        
        /* 避免发送过快 */
        usleep(10000);  /* 10ms */
    }

    LOG_INFO("所有chunk发送完成 (%d 个chunks)", chunk_num);
    free(entries);

 cleanup:
    if (path) free(path);
    if (request_id != default_request_id) free(request_id);
}

/* 处理打包并发送请求 */
static void handle_download_package(agent_context_t *ctx, const char *data)
{
    char *path = json_get_string(data, "path");
    char *format = json_get_string(data, "format");
    char *request_id = json_get_string(data, "request_id");
    
    // Check for the new "paths" array parameter for multiple files
    int paths_count = 0;
    char **paths_array = parse_json_string_array(data, "paths", &paths_count);
    
    if (!path && !paths_array) {
        LOG_ERROR("打包请求: 缺少path参数或paths参数");
        goto cleanup;
    }
    
    /* 生成临时归档文件 */
    char tmpfile[256];
    snprintf(tmpfile, sizeof(tmpfile), "/tmp/agent_pkg_%d_%llu", getpid(), (unsigned long long)get_timestamp_ms());
    char archive[320];
    int ret = -1;
    
    if (format && strcmp(format, "tar") == 0) {
        snprintf(archive, sizeof(archive), "%s.tar", tmpfile);
        char cmd[4096]; // Increased size for multiple files
        
        if (paths_array && paths_count > 0) {
            // Handle multiple files
            strcpy(cmd, "cd / && tar -cf '");
            strcat(cmd, archive);
            strcat(cmd, "' ");
            
            // Add each file to the command
            for (int i = 0; i < paths_count; i++) {
                const char *file_str = paths_array[i];
                if (file_str) {
                    // Normalize the path to prevent directory traversal
                    char normalized_path[2048];
                    normalize_path(file_str, normalized_path, sizeof(normalized_path));
                    
                    // Add to command ensuring proper escaping
                    char escaped_path[2048];
                    escape_shell_arg(normalized_path + 1, escaped_path, sizeof(escaped_path)); // Skip leading '/'
                    
                    // Check if file exists
                    struct stat st;
                    if (stat(normalized_path, &st) == 0) {
                        strcat(cmd, "'");
                        strcat(cmd, escaped_path);
                        strcat(cmd, "' ");
                        LOG_INFO("Adding to archive: %s", normalized_path);
                    } else {
                        LOG_WARN("File does not exist, skipping: %s", normalized_path);
                    }
                }
            }
            
            strcat(cmd, "2>&1");
        } else if (path) {
            // Handle single file (original logic)
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
            
            // For both files and directories, change to the parent directory first to preserve structure
            char parent_dir[2048];
            char item_name[512];
            strncpy(parent_dir, normalized_check, sizeof(parent_dir) - 1);
            parent_dir[sizeof(parent_dir) - 1] = '\0';
            
            // Extract the item name (last component)
            char *last_slash = strrchr(parent_dir, '/');
            if (last_slash && *(last_slash + 1) != '\0') {
                strcpy(item_name, last_slash + 1);
                *last_slash = '\0';  // Split parent dir
                // If parent_dir is empty after split, it was an absolute path like /filename
                if (parent_dir[0] == '\0') {
                    snprintf(cmd, sizeof(cmd), "cd / && tar -cf '%s' '%s' 2>&1", archive, item_name);
                } else {
                    snprintf(cmd, sizeof(cmd), "cd '%s' && tar -cf '%s' '%s' 2>&1", 
                            parent_dir, archive, item_name);
                }
            } else {
                // No slash found, so it's relative to root
                snprintf(cmd, sizeof(cmd), "cd / && tar -cf '%s' '%s' 2>&1", archive, normalized_check + 1);
            }
        } else {
            LOG_ERROR("打包请求: 无法处理路径参数");
            goto cleanup;
        }
        
        LOG_DEBUG("执行打包: %s", cmd);
        ret = system(cmd);
        if (ret != 0) {
            LOG_ERROR("tar命令失败: ret=%d, errno=%d", ret, errno);
            LOG_ERROR("命令: %s", cmd);
        } else {
            LOG_INFO("tar打包完成");
        }
    } else {
        snprintf(archive, sizeof(archive), "%s.zip", tmpfile);
        char cmd[4096]; // Increased size for multiple files
        
        if (paths_array && paths_count > 0) {
            // Handle multiple files for zip
            strcpy(cmd, "cd / && zip -rq '");
            strcat(cmd, archive);
            strcat(cmd, "' ");
            
            // Add each file to the command
            for (int i = 0; i < paths_count; i++) {
                const char *file_str = paths_array[i];
                if (file_str) {
                    // Normalize the path to prevent directory traversal
                    char normalized_path[2048];
                    normalize_path(file_str, normalized_path, sizeof(normalized_path));
                    
                    // Add to command ensuring proper escaping
                    char escaped_path[2048];
                    escape_shell_arg(normalized_path + 1, escaped_path, sizeof(escaped_path)); // Skip leading '/'
                    
                    // Check if file exists
                    struct stat st;
                    if (stat(normalized_path, &st) == 0) {
                        strcat(cmd, "'");
                        strcat(cmd, escaped_path);
                        strcat(cmd, "' ");
                        LOG_INFO("Adding to archive: %s", normalized_path);
                    } else {
                        LOG_WARN("File does not exist, skipping: %s", normalized_path);
                    }
                }
            }
            
            strcat(cmd, "2>&1");
        } else if (path) {
            // Handle single file (original logic)
            char normalized_check[2048];
            normalize_path(path, normalized_check, sizeof(normalized_check));
            
            /* 提取相对路径 */
            const char *rel_path = normalized_check;
            if (rel_path[0] == '/' && rel_path[1] != '\0') {
                rel_path = normalized_check + 1;
            }
            
            snprintf(cmd, sizeof(cmd), "cd / && zip -rq '%s' '%s' 2>&1", archive, rel_path);
        } else {
            LOG_ERROR("打包请求: 无法处理路径参数");
            goto cleanup;
        }
        
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

    // Read file into memory buffer (current approach - can be optimized for streaming later)
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
        
        #define CHUNK_SIZE  (48 * 1024)  /* 每块48KB base64数据 */
        size_t total_chunks = (encoded_len + CHUNK_SIZE - 1) / CHUNK_SIZE;
        
        LOG_INFO("分块发送打包响应: 文件=%s, 大小=%lld, 编码后=%zu, 总块数=%zu", 
                 filename, (long long)fsize, encoded_len, total_chunks);
        
        for (size_t chunk_idx = 0; chunk_idx < total_chunks; chunk_idx++) {
            size_t chunk_start = chunk_idx * CHUNK_SIZE;
            size_t chunk_end = (chunk_start + CHUNK_SIZE < encoded_len) ? chunk_start + CHUNK_SIZE : encoded_len;
            size_t chunk_len = chunk_end - chunk_start;
            
            char *json = malloc(chunk_len + 256);
            if (json && esc_filename) {
                int offset = 0;
                
                if (chunk_idx == 0) {
                    offset += snprintf(json + offset, chunk_len + 256 - offset,
                        "{\"filename\":\"%s\",\"size\":%lld,", esc_filename, (long long)fsize);
                } else {
                    offset += snprintf(json + offset, chunk_len + 256 - offset, "{");
                }
                
                offset += snprintf(json + offset, chunk_len + 256 - offset,
                    "\"content\":\"%.*s\"", (int)chunk_len, encoded + chunk_start);
                
                offset += snprintf(json + offset, chunk_len + 256 - offset,
                    ",\"chunk_index\":%zu,\"total_chunks\":%zu", chunk_idx, total_chunks);
                
                if (request_id) {
                    offset += snprintf(json + offset, chunk_len + 256 - offset, 
                        ",\"request_id\":\"%s\"", request_id);
                }
                
                if (chunk_idx == total_chunks - 1) {
                    snprintf(json + offset, chunk_len + 256 - offset, "}");
                } else {
                    snprintf(json + offset, chunk_len + 256 - offset, ",\"complete\":false}");
                }
                
                socket_send_json(ctx, MSG_TYPE_DOWNLOAD_PACKAGE, json);
                free(json);
            } else {
                LOG_ERROR("JSON缓冲区分配失败");
                break;
            }
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
    if (paths_array) {
        free_string_array(paths_array, paths_count);
    }
    if (path) free(path);
    if (format) free(format);
    if (request_id) free(request_id);
}

/* 处理命令请求 */
static void handle_cmd_request(agent_context_t *ctx, const char *data)
{
    char *cmd = json_get_string(data, "cmd");
    char *command = json_get_string(data, "command");
    char *request_id = json_get_string(data, "request_id");
    
    /* 兼容前端：优先使用 cmd，其次使用 command */
    char *actual_cmd = cmd ? cmd : command;
    
    if (!actual_cmd) {
        goto cleanup;
    }
    
    /* 内置命令处理 */
    if (strcmp(actual_cmd, "status") == 0) {
        /* 立即上报状态 */
        LOG_INFO("收到状态查询命令，开始收集系统信息");
        system_status_t status;
        status_collect(&status);
        char *json = status_to_json(&status);
        if (json) {
            char *final_json = NULL;
            if (request_id) {
                size_t json_len = strlen(json);
                size_t final_size = json_len + strlen(request_id) + 32;
                final_json = malloc(final_size);
                if (final_json) {
                    snprintf(final_json, final_size, "%.*s,\"request_id\":\"%s\"}", (int)(json_len - 1), json, request_id);
                    socket_send_json(ctx, MSG_TYPE_SYSTEM_STATUS, final_json);
                    free(final_json);
                }
            }
            if (!final_json) {
                socket_send_json(ctx, MSG_TYPE_SYSTEM_STATUS, json);
            }
            free(json);
            LOG_INFO("系统状态已上报");
        }
    } else if (strcmp(actual_cmd, "system_status") == 0) {
        /* 前端发送的 system_status 命令，同 status */
        LOG_INFO("收到 system_status 命令，开始收集系统信息");
        system_status_t status;
        status_collect(&status);
        char *json = status_to_json(&status);
        if (json) {
            char *final_json = NULL;
            if (request_id) {
                size_t json_len = strlen(json);
                size_t final_size = json_len + strlen(request_id) + 32;
                final_json = malloc(final_size);
                if (final_json) {
                    snprintf(final_json, final_size, "%.*s,\"request_id\":\"%s\"}", (int)(json_len - 1), json, request_id);
                    socket_send_json(ctx, MSG_TYPE_SYSTEM_STATUS, final_json);
                    free(final_json);
                }
            }
            if (!final_json) {
                socket_send_json(ctx, MSG_TYPE_SYSTEM_STATUS, json);
            }
            free(json);
            LOG_INFO("系统状态已上报");
        }
    } else if (strcmp(actual_cmd, "reboot") == 0) {
        LOG_WARN("收到重启命令");
        system("reboot");
    } else if (strcmp(actual_cmd, "pty_list") == 0) {
        pty_list_sessions(ctx);
    } else if (strcmp(actual_cmd, "script_list") == 0) {
        script_list(ctx);
    } else {
        /* 执行shell命令 */
        script_execute_inline(ctx, request_id ? request_id : "cmd", actual_cmd);
    }
    
cleanup:
    if (cmd) free(cmd);
    if (command) free(command);
    if (request_id) free(request_id);
}

/* 处理消息 */
int protocol_handle_message(agent_context_t *ctx, const char *data, size_t len)
{
    if (!ctx || !data || len < 1) return -1;

    /* 消息格式: 类型(1字节) + 长度(2字节,大端) + JSON数据 */
    if (len < 3) {
        LOG_ERROR("消息太短: %zu字节", len);
        return -1;
    }

    msg_type_t type = (msg_type_t)(unsigned char)data[0];
    uint16_t json_len = (data[1] << 8) | data[2];
    const char *json_data = data + 3;

    if (len < (size_t)(3 + json_len)) {
        LOG_ERROR("消息长度不匹配: 期望%u字节, 实际%zu字节", 3 + json_len, len);
        return -1;
    }

    LOG_DEBUG("收到消息: type=0x%02X, json_len=%u", (unsigned char)type, json_len);
    
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
    case MSG_TYPE_FILE_DOWNLOAD_DATA:
        tcp_handle_download_response(ctx, data, len);
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
        
    case MSG_TYPE_UPDATE_CHECK:
        /* 更新检查请求 */
        LOG_INFO("收到更新检查请求");
        break;
        
    case MSG_TYPE_UPDATE_INFO:
        /* 更新信息响应 */
        {
            char *has_update_str = json_get_string(json_data, "has_update");
            char *latest_version = json_get_string(json_data, "latest_version");
            char *download_url = json_get_string(json_data, "download_url");
            char *md5_checksum = json_get_string(json_data, "md5_checksum");
            char *release_notes = json_get_string(json_data, "release_notes");
            int mandatory = json_get_bool(json_data, "mandatory", false);
            
            if (!has_update_str || strcmp(has_update_str, "true") != 0) {
                LOG_INFO("当前版本已是最新: %s", AGENT_VERSION);
                break;
            }
            
            LOG_INFO("发现新版本: %s", latest_version);
            LOG_INFO("下载URL: %s", download_url);
            LOG_INFO("MD5校验和: %s", md5_checksum);
            LOG_INFO("更新说明: %s", release_notes);
            LOG_INFO("是否强制更新: %s", mandatory ? "是" : "否");
            
            /* 如果配置了自动确认，或者强制更新，自动请求下载 */
            if ((!g_agent_ctx->config.update_require_confirm) || mandatory) {
                LOG_INFO("自动请求下载更新");
                /* 发送下载请求 */
                char *json = malloc(256);
                snprintf(json, 256,
                         "{\"version\":\"%s\",\"request_id\":\"update-%lld\"}",
                         latest_version, (long long)get_timestamp_ms());
                int rc = socket_send_json(ctx, MSG_TYPE_UPDATE_DOWNLOAD, json);
                free(json);
                
                if (rc != 0) {
                    LOG_ERROR("发送下载请求失败");
                }
            } else {
                LOG_INFO("等待服务器批准下载");
            }
            break;
        }
        
    case MSG_TYPE_UPDATE_APPROVE:
        /* 服务器批准下载，提供下载URL */
        {
            LOG_INFO("收到下载批准");
            char *download_url = json_get_string(json_data, "download_url");
            char *request_id = json_get_string(json_data, "request_id");
            
            if (!download_url) {
                LOG_ERROR("下载URL为空");
                /* 发送错误通知 */
                char *error_json = malloc(256);
                snprintf(error_json, 256,
                         "{\"status\":\"failed\",\"error\":\"no_download_url\",\"request_id\":\"%s\"}",
                         request_id ? request_id : "unknown");
                socket_send_json(ctx, MSG_TYPE_UPDATE_ERROR, error_json);
                free(error_json);
                break;
            }
            
            /* 准备下载路径 */
            char download_path[512];
            char temp_dir[512];
            time_t now = time(NULL);
            snprintf(temp_dir, sizeof(temp_dir), "%s/%lld",
                     g_agent_ctx->config.update_temp_path, (long long)now);
            snprintf(download_path, sizeof(download_path),
                     "%s/agent-update-%lld.tar",
                     temp_dir, (long long)now);
            
            /* 创建临时目录 */
            mkdir_recursive(temp_dir, 0755);
            
            /* 开始下载 */
            int rc = update_download_package(
                download_url,
                download_path,
                download_progress_callback,
                g_agent_ctx
            );
            
            if (rc == 0) {
                LOG_INFO("下载成功，开始安装");
                
                /* 发送进度：下载完成 */
                char *progress_json = malloc(256);
                snprintf(progress_json, 256,
                         "{\"status\":\"downloaded\",\"request_id\":\"%s\",\"progress\":100}",
                         request_id ? request_id : "unknown");
                socket_send_json(ctx, MSG_TYPE_UPDATE_PROGRESS, progress_json);
                free(progress_json);
                
                /* 发送安装通知 */
                char *install_json = malloc(256);
                snprintf(install_json, 256,
                         "{\"status\":\"installing\",\"request_id\":\"%s\",\"path\":\"%s\"}",
                         request_id ? request_id : "unknown",
                         download_path);
                socket_send_json(ctx, MSG_TYPE_UPDATE_PROGRESS, install_json);
                free(install_json);
                
                /* 开始安装 */
                update_install_package(download_path);
            } else {
                LOG_ERROR("下载失败");
                
                /* 发送错误通知 */
                char *error_json = malloc(256);
                snprintf(error_json, 256,
                         "{\"status\":\"failed\",\"error\":\"download_failed\",\"request_id\":\"%s\"}",
                         request_id ? request_id : "unknown");
                socket_send_json(ctx, MSG_TYPE_UPDATE_ERROR, error_json);
                free(error_json);
            }
            break;
        }
        
    case MSG_TYPE_UPDATE_PROGRESS:
        /* 更新进度上报 */
        {
            char *status = json_get_string(json_data, "status");
            int progress = json_get_int(json_data, "progress", 0);
            
            LOG_INFO("更新状态: %s, 进度: %d%%", status, progress);
            break;
        }
        
    case MSG_TYPE_UPDATE_COMPLETE:
        /* 更新完成，服务器通知重启 */
        {
            char *new_version = json_get_string(json_data, "new_version");
            LOG_INFO("收到更新完成通知，新版本: %s", new_version);
            
            /* 准备重启 */
            sleep(2);
            update_restart_agent();
            break;
        }
        
    case MSG_TYPE_UPDATE_ERROR:
        /* 更新错误通知 */
        {
            char *error = json_get_string(json_data, "error");
            char *status = json_get_string(json_data, "status");
            
            LOG_ERROR("更新错误: %s", error);
            
            /* 如果配置了自动回滚，执行回滚 */
            if (g_agent_ctx && g_agent_ctx->config.update_rollback_on_fail) {
                LOG_INFO("自动回滚到旧版本");
                
                char last_backup_path[512];
                FILE *fp = fopen("/var/lib/agent/backup/.last_backup", "r");
                if (fp) {
                    if (fgets(last_backup_path, sizeof(last_backup_path), fp)) {
                        /* 去除换行符 */
                        char *newline = strchr(last_backup_path, '\n');
                        if (newline) *newline = '\0';
                    }
                    fclose(fp);
                    
                    if (strlen(last_backup_path) > 0) {
                        update_rollback_to_backup(last_backup_path);
                    }
                }
            }
            
            break;
        }
        
    case MSG_TYPE_UPDATE_ROLLBACK:
        /* 服务器通知回滚 */
        {
            LOG_INFO("收到回滚指令");
            /* 服务器会指定回滚到的版本或备份 */
            char *backup_path = json_get_string(json_data, "backup_path");
            
            if (backup_path && strlen(backup_path) > 0) {
                LOG_INFO("回滚到: %s", backup_path);
                update_rollback_to_backup(backup_path);
            } else {
                LOG_WARN("回滚路径为空，尝试自动回滚");
                char last_backup_path[512];
                FILE *fp = fopen("/var/lib/agent/backup/.last_backup", "r");
                if (fp) {
                    if (fgets(last_backup_path, sizeof(last_backup_path), fp)) {
                        char *newline = strchr(last_backup_path, '\n');
                        if (newline) *newline = '\0';
                    }
                    fclose(fp);
                    
                    if (strlen(last_backup_path) > 0) {
                        update_rollback_to_backup(last_backup_path);
                    }
                }
            }
            }
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
