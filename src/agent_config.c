/*
 * 配置管理模块
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <sys/stat.h>
#include "agent.h"

/* 设置默认配置 */
void config_set_defaults(agent_config_t *config)
{
    if (!config) return;
    
    memset(config, 0, sizeof(agent_config_t));
    
    strncpy(config->server_url, DEFAULT_SERVER_URL, sizeof(config->server_url) - 1);
    strncpy(config->log_path, DEFAULT_LOG_PATH, sizeof(config->log_path) - 1);
    strncpy(config->script_path, DEFAULT_SCRIPT_PATH, sizeof(config->script_path) - 1);
    
    /* 获取设备ID */
    char *device_id = get_device_id();
    if (device_id) {
        strncpy(config->device_id, device_id, sizeof(config->device_id) - 1);
    }
    
    config->heartbeat_interval = DEFAULT_HEARTBEAT_SEC;
    config->reconnect_interval = DEFAULT_RECONNECT_SEC;
    config->status_interval = 60;  /* 默认60秒上报一次状态 */
    config->enable_pty = true;
    config->enable_script = true;
    config->log_level = LOG_LEVEL_INFO;
}

/* 解析配置行 */
static int parse_config_line(agent_config_t *config, const char *key, const char *value)
{
    if (strcmp(key, "server_url") == 0) {
        strncpy(config->server_url, value, sizeof(config->server_url) - 1);
    } else if (strcmp(key, "device_id") == 0) {
        strncpy(config->device_id, value, sizeof(config->device_id) - 1);
    } else if (strcmp(key, "auth_token") == 0) {
        strncpy(config->auth_token, value, sizeof(config->auth_token) - 1);
    } else if (strcmp(key, "heartbeat_interval") == 0) {
        config->heartbeat_interval = atoi(value);
    } else if (strcmp(key, "reconnect_interval") == 0) {
        config->reconnect_interval = atoi(value);
    } else if (strcmp(key, "status_interval") == 0) {
        config->status_interval = atoi(value);
    } else if (strcmp(key, "log_path") == 0) {
        strncpy(config->log_path, value, sizeof(config->log_path) - 1);
    } else if (strcmp(key, "script_path") == 0) {
        strncpy(config->script_path, value, sizeof(config->script_path) - 1);
    } else if (strcmp(key, "enable_pty") == 0) {
        config->enable_pty = (strcmp(value, "true") == 0 || strcmp(value, "1") == 0);
    } else if (strcmp(key, "enable_script") == 0) {
        config->enable_script = (strcmp(value, "true") == 0 || strcmp(value, "1") == 0);
    } else if (strcmp(key, "log_level") == 0) {
        if (strcmp(value, "debug") == 0) config->log_level = LOG_LEVEL_DEBUG;
        else if (strcmp(value, "info") == 0) config->log_level = LOG_LEVEL_INFO;
        else if (strcmp(value, "warn") == 0) config->log_level = LOG_LEVEL_WARN;
        else if (strcmp(value, "error") == 0) config->log_level = LOG_LEVEL_ERROR;
        else config->log_level = atoi(value);
    } else {
        return -1;  /* 未知配置项 */
    }
    
    return 0;
}

/* 加载配置文件 */
int config_load(agent_config_t *config, const char *path)
{
    if (!config || !path) return -1;
    
    /* 先设置默认值 */
    config_set_defaults(config);
    
    FILE *fp = fopen(path, "r");
    if (!fp) {
        LOG_WARN("配置文件不存在，使用默认配置: %s", path);
        return 0;  /* 使用默认配置 */
    }
    
    char line[512];
    int line_num = 0;
    
    while (fgets(line, sizeof(line), fp)) {
        line_num++;
        
        /* 去除首尾空格 */
        char *p = line;
        while (*p && isspace(*p)) p++;
        
        /* 跳过空行和注释 */
        if (*p == '\0' || *p == '#' || *p == ';') {
            continue;
        }
        
        /* 去除尾部换行和空格 */
        char *end = p + strlen(p) - 1;
        while (end > p && (isspace(*end) || *end == '\n' || *end == '\r')) {
            *end-- = '\0';
        }
        
        /* 解析 key = value */
        char *eq = strchr(p, '=');
        if (!eq) {
            LOG_WARN("配置文件格式错误 (行 %d): %s", line_num, line);
            continue;
        }
        
        *eq = '\0';
        char *key = p;
        char *value = eq + 1;
        
        /* 去除key尾部空格 */
        end = key + strlen(key) - 1;
        while (end > key && isspace(*end)) {
            *end-- = '\0';
        }
        
        /* 去除value首部空格 */
        while (*value && isspace(*value)) value++;
        
        /* 去除value的引号 */
        if (*value == '"' || *value == '\'') {
            char quote = *value;
            value++;
            char *quote_end = strrchr(value, quote);
            if (quote_end) *quote_end = '\0';
        }
        
        if (parse_config_line(config, key, value) != 0) {
            LOG_WARN("未知配置项 (行 %d): %s", line_num, key);
        }
    }
    
    fclose(fp);
    
    LOG_INFO("配置文件已加载: %s", path);
    return 0;
}

/* 保存配置文件 */
int config_save(agent_config_t *config, const char *path)
{
    if (!config || !path) return -1;
    
    /* 确保目录存在 */
    char dir[256];
    strncpy(dir, path, sizeof(dir) - 1);
    char *last_slash = strrchr(dir, '/');
    if (last_slash) {
        *last_slash = '\0';
        mkdir_recursive(dir, 0755);
    }
    
    FILE *fp = fopen(path, "w");
    if (!fp) {
        LOG_ERROR("无法创建配置文件: %s", path);
        return -1;
    }
    
    fprintf(fp, "# Buildroot Agent Configuration\n");
    fprintf(fp, "# Generated automatically\n\n");
    
    fprintf(fp, "# 服务器地址 (WebSocket)\n");
    fprintf(fp, "server_url = \"%s\"\n\n", config->server_url);
    
    fprintf(fp, "# 设备ID (唯一标识)\n");
    fprintf(fp, "device_id = \"%s\"\n\n", config->device_id);
    
    fprintf(fp, "# 认证Token\n");
    fprintf(fp, "auth_token = \"%s\"\n\n", config->auth_token);
    
    fprintf(fp, "# 心跳间隔 (秒)\n");
    fprintf(fp, "heartbeat_interval = %d\n\n", config->heartbeat_interval);
    
    fprintf(fp, "# 重连间隔 (秒)\n");
    fprintf(fp, "reconnect_interval = %d\n\n", config->reconnect_interval);
    
    fprintf(fp, "# 状态上报间隔 (秒)\n");
    fprintf(fp, "status_interval = %d\n\n", config->status_interval);
    
    fprintf(fp, "# 日志目录\n");
    fprintf(fp, "log_path = \"%s\"\n\n", config->log_path);
    
    fprintf(fp, "# 脚本存放目录\n");
    fprintf(fp, "script_path = \"%s\"\n\n", config->script_path);
    
    fprintf(fp, "# 是否启用PTY (远程Shell)\n");
    fprintf(fp, "enable_pty = %s\n\n", config->enable_pty ? "true" : "false");
    
    fprintf(fp, "# 是否启用脚本执行\n");
    fprintf(fp, "enable_script = %s\n\n", config->enable_script ? "true" : "false");
    
    fprintf(fp, "# 日志级别 (debug, info, warn, error)\n");
    const char *level_str = "info";
    switch (config->log_level) {
        case LOG_LEVEL_DEBUG: level_str = "debug"; break;
        case LOG_LEVEL_INFO: level_str = "info"; break;
        case LOG_LEVEL_WARN: level_str = "warn"; break;
        case LOG_LEVEL_ERROR: level_str = "error"; break;
    }
    fprintf(fp, "log_level = %s\n", level_str);
    
    fclose(fp);
    
    LOG_INFO("配置文件已保存: %s", path);
    return 0;
}

/* 打印配置信息 */
void config_print(agent_config_t *config)
{
    if (!config) return;
    
    LOG_INFO("========== 当前配置 ==========");
    LOG_INFO("服务器地址: %s", config->server_url);
    LOG_INFO("设备ID: %s", config->device_id);
    LOG_INFO("心跳间隔: %d秒", config->heartbeat_interval);
    LOG_INFO("重连间隔: %d秒", config->reconnect_interval);
    LOG_INFO("状态上报间隔: %d秒", config->status_interval);
    LOG_INFO("日志目录: %s", config->log_path);
    LOG_INFO("脚本目录: %s", config->script_path);
    LOG_INFO("PTY功能: %s", config->enable_pty ? "启用" : "禁用");
    LOG_INFO("脚本执行: %s", config->enable_script ? "启用" : "禁用");
    LOG_INFO("==============================");
}
