/*
 * 协议处理模块
 * 解析和处理WebSocket消息
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "agent.h"

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
    msg_type_t type = (msg_type_t)data[0];
    const char *json_data = data + 1;
    
    LOG_DEBUG("收到消息: type=0x%02X, len=%zu", type, len);
    
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
        
    case MSG_TYPE_CMD_REQUEST:
        handle_cmd_request(ctx, json_data);
        break;
        
    case MSG_TYPE_HEARTBEAT:
        /* 心跳响应 */
        LOG_DEBUG("收到心跳响应");
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
        "\"timestamp\":%llu"
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
        "{\"timestamp\":%llu,\"uptime\":%u}",
        get_timestamp_ms(),
        (unsigned int)(time(NULL)));  /* 简单起见用当前时间 */
    
    return json;
}
