/*
 * 配置管理模块
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <sys/stat.h>
#include <errno.h>
#include "agent.h"

static void set_string_field(char *dest, size_t dest_size, const char *value)
{
    if (value && dest && dest_size > 0) {
        strncpy(dest, value, dest_size - 1);
        dest[dest_size - 1] = '\0';
    }
}

void config_set_defaults(agent_config_t *config)
{
    if (!config) return;
    
    memset(config, 0, sizeof(agent_config_t));
    
    set_string_field(config->server_addr, sizeof(config->server_addr), DEFAULT_SERVER_ADDR);
    set_string_field(config->log_path, sizeof(config->log_path), DEFAULT_LOG_PATH);
    set_string_field(config->script_path, sizeof(config->script_path), DEFAULT_SCRIPT_PATH);
    set_string_field(config->version, sizeof(config->version), "1.0.0");
    
    config->heartbeat_interval = DEFAULT_HEARTBEAT_SEC;
    config->reconnect_interval = DEFAULT_RECONNECT_SEC;
    config->status_interval = 60;
    config->enable_pty = true;
    config->enable_script = true;
    config->log_level = LOG_LEVEL_INFO;
    
    config->enable_auto_update = false;
    config->update_check_interval = DEFAULT_UPDATE_CHECK_INTERVAL;
    set_string_field(config->update_channel, sizeof(config->update_channel), DEFAULT_UPDATE_CHANNEL);
    config->update_require_confirm = true;
    set_string_field(config->update_temp_path, sizeof(config->update_temp_path), DEFAULT_UPDATE_TEMP_PATH);
    set_string_field(config->update_backup_path, sizeof(config->update_backup_path), DEFAULT_UPDATE_BACKUP_PATH);
    config->update_rollback_on_fail = true;
    config->update_rollback_timeout = DEFAULT_UPDATE_ROLLBACK_TIMEOUT;
    config->update_verify_checksum = true;
    config->update_ca_cert_path[0] = '\0';
}

void config_apply_overrides(agent_config_t *config, const config_override_t *overrides)
{
    if (!config || !overrides) return;
    
    if (overrides->server_addr) {
        set_string_field(config->server_addr, sizeof(config->server_addr), overrides->server_addr);
    }
    if (overrides->device_id) {
        set_string_field(config->device_id, sizeof(config->device_id), overrides->device_id);
    }
    if (overrides->auth_token) {
        set_string_field(config->auth_token, sizeof(config->auth_token), overrides->auth_token);
    }
    if (overrides->log_path) {
        set_string_field(config->log_path, sizeof(config->log_path), overrides->log_path);
    }
    if (overrides->script_path) {
        set_string_field(config->script_path, sizeof(config->script_path), overrides->script_path);
    }
    if (overrides->log_level_set) {
        config->log_level = overrides->log_level;
    }
    if (overrides->use_ssl_set) {
        config->use_ssl = overrides->use_ssl;
    }
    if (overrides->ca_path) {
        set_string_field(config->ca_path, sizeof(config->ca_path), overrides->ca_path);
    }
}

void config_load_from_env(agent_config_t *config)
{
    if (!config) return;
    
    const char *val;
    
    val = getenv("BUILDROOT_SERVER_ADDR");
    if (val) {
        set_string_field(config->server_addr, sizeof(config->server_addr), val);
    }
    
    val = getenv("BUILDROOT_DEVICE_ID");
    if (val) {
        set_string_field(config->device_id, sizeof(config->device_id), val);
    }
    
    val = getenv("BUILDROOT_AUTH_TOKEN");
    if (val) {
        set_string_field(config->auth_token, sizeof(config->auth_token), val);
    }
    
    val = getenv("BUILDROOT_LOG_PATH");
    if (val) {
        set_string_field(config->log_path, sizeof(config->log_path), val);
    }
    
    val = getenv("BUILDROOT_SCRIPT_PATH");
    if (val) {
        set_string_field(config->script_path, sizeof(config->script_path), val);
    }
    
    val = getenv("BUILDROOT_LOG_LEVEL");
    if (val) {
        if (strcmp(val, "debug") == 0) config->log_level = LOG_LEVEL_DEBUG;
        else if (strcmp(val, "info") == 0) config->log_level = LOG_LEVEL_INFO;
        else if (strcmp(val, "warn") == 0) config->log_level = LOG_LEVEL_WARN;
        else if (strcmp(val, "error") == 0) config->log_level = LOG_LEVEL_ERROR;
        else config->log_level = atoi(val);
    }
    
    val = getenv("BUILDROOT_USE_SSL");
    if (val) {
        config->use_ssl = (strcmp(val, "true") == 0 || strcmp(val, "1") == 0);
    }
    
    val = getenv("BUILDROOT_CA_PATH");
    if (val) {
        set_string_field(config->ca_path, sizeof(config->ca_path), val);
    }
    
    val = getenv("BUILDROOT_HEARTBEAT_INTERVAL");
    if (val) {
        int interval = atoi(val);
        if (interval > 0) config->heartbeat_interval = interval;
    }
    
    val = getenv("BUILDROOT_RECONNECT_INTERVAL");
    if (val) {
        int interval = atoi(val);
        if (interval > 0) config->reconnect_interval = interval;
    }
    
    val = getenv("BUILDROOT_STATUS_INTERVAL");
    if (val) {
        int interval = atoi(val);
        if (interval > 0) config->status_interval = interval;
    }
    
    val = getenv("BUILDROOT_ENABLE_AUTO_UPDATE");
    if (val) {
        config->enable_auto_update = (strcmp(val, "true") == 0 || strcmp(val, "1") == 0);
    }
    
    val = getenv("BUILDROOT_UPDATE_CHANNEL");
    if (val) {
        set_string_field(config->update_channel, sizeof(config->update_channel), val);
    }
}

int config_validate(agent_config_t *config)
{
    if (!config) return -1;
    
    if (config->heartbeat_interval <= 0) {
        config->heartbeat_interval = DEFAULT_HEARTBEAT_SEC;
    }
    if (config->reconnect_interval <= 0) {
        config->reconnect_interval = DEFAULT_RECONNECT_SEC;
    }
    if (config->status_interval <= 0) {
        config->status_interval = 60;
    }
    if (config->update_check_interval <= 0) {
        config->update_check_interval = DEFAULT_UPDATE_CHECK_INTERVAL;
    }
    if (config->update_rollback_timeout <= 0) {
        config->update_rollback_timeout = DEFAULT_UPDATE_ROLLBACK_TIMEOUT;
    }
    
    if (config->log_level < LOG_LEVEL_DEBUG || config->log_level > LOG_LEVEL_ERROR) {
        config->log_level = LOG_LEVEL_INFO;
    }
    
    if (config->server_addr[0] == '\0') {
        set_string_field(config->server_addr, sizeof(config->server_addr), DEFAULT_SERVER_ADDR);
    }
    
    if (config->device_id[0] == '\0') {
        char *device_id = get_device_id();
        if (device_id) {
            set_string_field(config->device_id, sizeof(config->device_id), device_id);
        }
    }
    
    return 0;
}

static int parse_config_line(agent_config_t *config, const char *key, const char *value)
{
    if (strcmp(key, "server_addr") == 0) {
        set_string_field(config->server_addr, sizeof(config->server_addr), value);
    } else if (strcmp(key, "device_id") == 0) {
        set_string_field(config->device_id, sizeof(config->device_id), value);
    } else if (strcmp(key, "version") == 0) {
        set_string_field(config->version, sizeof(config->version), value);
    } else if (strcmp(key, "auth_token") == 0) {
        set_string_field(config->auth_token, sizeof(config->auth_token), value);
    } else if (strcmp(key, "heartbeat_interval") == 0) {
        config->heartbeat_interval = atoi(value);
    } else if (strcmp(key, "reconnect_interval") == 0) {
        config->reconnect_interval = atoi(value);
    } else if (strcmp(key, "status_interval") == 0) {
        config->status_interval = atoi(value);
    } else if (strcmp(key, "log_path") == 0) {
        set_string_field(config->log_path, sizeof(config->log_path), value);
    } else if (strcmp(key, "script_path") == 0) {
        set_string_field(config->script_path, sizeof(config->script_path), value);
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
    } else if (strcmp(key, "use_ssl") == 0) {
        config->use_ssl = (strcmp(value, "true") == 0 || strcmp(value, "1") == 0);
    } else if (strcmp(key, "ca_path") == 0) {
        set_string_field(config->ca_path, sizeof(config->ca_path), value);
    } else if (strcmp(key, "enable_auto_update") == 0) {
        config->enable_auto_update = (strcmp(value, "true") == 0 || strcmp(value, "1") == 0);
    } else if (strcmp(key, "update_check_interval") == 0) {
        config->update_check_interval = atoi(value);
    } else if (strcmp(key, "update_channel") == 0) {
        set_string_field(config->update_channel, sizeof(config->update_channel), value);
    } else if (strcmp(key, "update_require_confirm") == 0) {
        config->update_require_confirm = (strcmp(value, "true") == 0 || strcmp(value, "1") == 0);
    } else if (strcmp(key, "update_temp_path") == 0) {
        set_string_field(config->update_temp_path, sizeof(config->update_temp_path), value);
    } else if (strcmp(key, "update_backup_path") == 0) {
        set_string_field(config->update_backup_path, sizeof(config->update_backup_path), value);
    } else if (strcmp(key, "update_rollback_on_fail") == 0) {
        config->update_rollback_on_fail = (strcmp(value, "true") == 0 || strcmp(value, "1") == 0);
    } else if (strcmp(key, "update_rollback_timeout") == 0) {
        config->update_rollback_timeout = atoi(value);
    } else if (strcmp(key, "update_verify_checksum") == 0) {
        config->update_verify_checksum = (strcmp(value, "true") == 0 || strcmp(value, "1") == 0);
    } else if (strcmp(key, "update_ca_cert_path") == 0) {
        set_string_field(config->update_ca_cert_path, sizeof(config->update_ca_cert_path), value);
    } else {
        return -1;
    }
    
    return 0;
}

config_load_result_t config_load(agent_config_t *config, const char *path)
{
    if (!config || !path) return CONFIG_LOAD_PARSE_ERROR;
    
    config_set_defaults(config);
    
    FILE *fp = fopen(path, "r");
    if (!fp) {
        return CONFIG_LOAD_NOT_FOUND;
    }
    
    char line[512];
    int line_num = 0;
    int parse_errors = 0;
    
    while (fgets(line, sizeof(line), fp)) {
        line_num++;
        
        char *p = line;
        while (*p && isspace((unsigned char)*p)) p++;
        
        if (*p == '\0' || *p == '#' || *p == ';') {
            continue;
        }
        
        char *end = p + strlen(p) - 1;
        while (end > p && (isspace((unsigned char)*end) || *end == '\n' || *end == '\r')) {
            *end-- = '\0';
        }
        
        char *eq = strchr(p, '=');
        if (!eq) {
            LOG_WARN("配置文件格式错误 (行 %d): %s", line_num, line);
            parse_errors++;
            continue;
        }
        
        *eq = '\0';
        char *key = p;
        char *value = eq + 1;
        
        end = key + strlen(key) - 1;
        while (end > key && isspace((unsigned char)*end)) {
            *end-- = '\0';
        }
        
        while (*value && isspace((unsigned char)*value)) value++;
        
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
    
    if (parse_errors > 0) {
        LOG_WARN("配置文件有 %d 个解析错误", parse_errors);
    }
    
    LOG_INFO("配置文件已加载: %s", path);
    return CONFIG_LOAD_OK;
}

int config_save(agent_config_t *config, const char *path)
{
    if (!config || !path) return -1;
    
    char dir[256];
    strncpy(dir, path, sizeof(dir) - 1);
    dir[sizeof(dir) - 1] = '\0';
    char *last_slash = strrchr(dir, '/');
    if (last_slash) {
        *last_slash = '\0';
        mkdir_recursive(dir, 0755);
    }
    
    FILE *fp = fopen(path, "w");
    if (!fp) {
        LOG_ERROR("无法创建配置文件: %s (%s)", path, strerror(errno));
        return -1;
    }
    
    fprintf(fp, "# Buildroot Agent Configuration\n");
    fprintf(fp, "# Generated automatically\n\n");
    
    fprintf(fp, "# 服务器地址 (host:port)\n");
    fprintf(fp, "server_addr = \"%s\"\n\n", config->server_addr);
    
    fprintf(fp, "# 设备ID (唯一标识)\n");
    fprintf(fp, "device_id = \"%s\"\n\n", config->device_id);

    fprintf(fp, "# Token（已废弃，保留用于向后兼容）\n");
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
    fprintf(fp, "log_level = %s\n\n", level_str);
    
    fprintf(fp, "# SSL配置\n");
    fprintf(fp, "use_ssl = %s\n", config->use_ssl ? "true" : "false");
    if (config->ca_path[0] != '\0') {
        fprintf(fp, "ca_path = \"%s\"\n", config->ca_path);
    }
    fprintf(fp, "\n");
    
    fprintf(fp, "# 自动更新配置\n");
    fprintf(fp, "enable_auto_update = %s\n", config->enable_auto_update ? "true" : "false");
    fprintf(fp, "update_check_interval = %d\n", config->update_check_interval);
    fprintf(fp, "update_channel = \"%s\"\n", config->update_channel);
    fprintf(fp, "update_require_confirm = %s\n", config->update_require_confirm ? "true" : "false");
    fprintf(fp, "update_temp_path = \"%s\"\n", config->update_temp_path);
    fprintf(fp, "update_backup_path = \"%s\"\n", config->update_backup_path);
    fprintf(fp, "update_rollback_on_fail = %s\n", config->update_rollback_on_fail ? "true" : "false");
    fprintf(fp, "update_rollback_timeout = %d\n", config->update_rollback_timeout);
    fprintf(fp, "update_verify_checksum = %s\n", config->update_verify_checksum ? "true" : "false");
    if (config->update_ca_cert_path[0] != '\0') {
        fprintf(fp, "update_ca_cert_path = \"%s\"\n", config->update_ca_cert_path);
    }
    
    fclose(fp);
    
    LOG_INFO("配置文件已保存: %s", path);
    return 0;
}

int config_save_example(agent_config_t *config, const char *path)
{
    if (!config || !path) return -1;
    
    char dir[256];
    strncpy(dir, path, sizeof(dir) - 1);
    dir[sizeof(dir) - 1] = '\0';
    char *last_slash = strrchr(dir, '/');
    if (last_slash) {
        *last_slash = '\0';
        mkdir_recursive(dir, 0755);
    }
    
    FILE *fp = fopen(path, "w");
    if (!fp) {
        LOG_ERROR("无法创建配置文件: %s (%s)", path, strerror(errno));
        return -1;
    }
    
    fprintf(fp, "# Buildroot Agent Configuration\n");
    fprintf(fp, "# \n");
    fprintf(fp, "# 使用说明：\n");
    fprintf(fp, "# 1. 复制此文件为 agent.conf: cp agent.conf.example agent.conf\n");
    fprintf(fp, "# 2. 根据实际情况修改配置项\n");
    fprintf(fp, "# 3. 运行 agent: ./buildroot-agent -c ./agent.conf\n");
    fprintf(fp, "# \n");
    fprintf(fp, "# 此文件由程序自动生成，请勿手动编辑默认值\n");
    fprintf(fp, "# 修改默认值请编辑 include/agent.h 中的 DEFAULT_* 宏定义\n\n");
    
    fprintf(fp, "# ========================================\n");
    fprintf(fp, "# 基础配置\n");
    fprintf(fp, "# ========================================\n\n");
    
    fprintf(fp, "# 服务器地址 (host:port)\n");
    fprintf(fp, "server_addr = \"%s\"\n\n", config->server_addr);
    
    fprintf(fp, "# 设备ID (唯一标识，留空则自动生成)\n");
    fprintf(fp, "device_id = \"%s\"\n\n", config->device_id);
    
    fprintf(fp, "# Agent版本\n");
    fprintf(fp, "version = \"%s\"\n\n", config->version);
    
    fprintf(fp, "# Token（已废弃，保留用于向后兼容）\n");
    fprintf(fp, "# auth_token = \"%s\"\n\n", config->auth_token);
    
    fprintf(fp, "# ========================================\n");
    fprintf(fp, "# 连接配置\n");
    fprintf(fp, "# ========================================\n\n");
    
    fprintf(fp, "# 心跳间隔 (秒)\n");
    fprintf(fp, "heartbeat_interval = %d\n\n", config->heartbeat_interval);
    
    fprintf(fp, "# 重连间隔 (秒)\n");
    fprintf(fp, "reconnect_interval = %d\n\n", config->reconnect_interval);
    
    fprintf(fp, "# 状态上报间隔 (秒)\n");
    fprintf(fp, "status_interval = %d\n\n", config->status_interval);
    
    fprintf(fp, "# ========================================\n");
    fprintf(fp, "# 路径配置\n");
    fprintf(fp, "# ========================================\n\n");
    
    fprintf(fp, "# 日志目录\n");
    fprintf(fp, "log_path = \"%s\"\n\n", config->log_path);
    
    fprintf(fp, "# 脚本存放目录\n");
    fprintf(fp, "script_path = \"%s\"\n\n", config->script_path);
    
    fprintf(fp, "# ========================================\n");
    fprintf(fp, "# 功能开关\n");
    fprintf(fp, "# ========================================\n\n");
    
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
    fprintf(fp, "log_level = %s\n\n", level_str);
    
    fprintf(fp, "# ========================================\n");
    fprintf(fp, "# SSL配置\n");
    fprintf(fp, "# ========================================\n\n");
    
    fprintf(fp, "# 是否启用SSL加密\n");
    fprintf(fp, "use_ssl = %s\n\n", config->use_ssl ? "true" : "false");
    
    fprintf(fp, "# CA证书路径 (可选，留空使用系统证书)\n");
    fprintf(fp, "ca_path = \"%s\"\n\n", config->ca_path);
    
    fprintf(fp, "# ========================================\n");
    fprintf(fp, "# 自动更新配置\n");
    fprintf(fp, "# ========================================\n\n");
    
    fprintf(fp, "# 是否启用自动更新\n");
    fprintf(fp, "enable_auto_update = %s\n\n", config->enable_auto_update ? "true" : "false");
    
    fprintf(fp, "# 更新检查间隔 (秒)\n");
    fprintf(fp, "update_check_interval = %d\n\n", config->update_check_interval);
    
    fprintf(fp, "# 更新渠道 (stable/beta/dev)\n");
    fprintf(fp, "update_channel = \"%s\"\n\n", config->update_channel);
    
    fprintf(fp, "# 更新前是否需要确认\n");
    fprintf(fp, "update_require_confirm = %s\n\n", config->update_require_confirm ? "true" : "false");
    
    fprintf(fp, "# 临时文件路径\n");
    fprintf(fp, "update_temp_path = \"%s\"\n\n", config->update_temp_path);
    
    fprintf(fp, "# 备份路径\n");
    fprintf(fp, "update_backup_path = \"%s\"\n\n", config->update_backup_path);
    
    fprintf(fp, "# 失败是否自动回滚\n");
    fprintf(fp, "update_rollback_on_fail = %s\n\n", config->update_rollback_on_fail ? "true" : "false");
    
    fprintf(fp, "# 回滚超时 (秒)\n");
    fprintf(fp, "update_rollback_timeout = %d\n\n", config->update_rollback_timeout);
    
    fprintf(fp, "# 是否校验文件校验和\n");
    fprintf(fp, "update_verify_checksum = %s\n\n", config->update_verify_checksum ? "true" : "false");
    
    fprintf(fp, "# 更新CA证书路径 (可选，留空使用系统证书)\n");
    fprintf(fp, "update_ca_cert_path = \"%s\"\n", config->update_ca_cert_path);
    
    fclose(fp);
    
    LOG_INFO("配置示例文件已保存: %s", path);
    return 0;
}

void config_print(agent_config_t *config)
{
    if (!config) return;
    
    LOG_INFO("========== 当前配置 ==========");
    LOG_INFO("服务器地址: %s", config->server_addr);
    LOG_INFO("设备ID: %s", config->device_id);
    LOG_INFO("心跳间隔: %d秒", config->heartbeat_interval);
    LOG_INFO("重连间隔: %d秒", config->reconnect_interval);
    LOG_INFO("状态上报间隔: %d秒", config->status_interval);
    LOG_INFO("日志目录: %s", config->log_path);
    LOG_INFO("脚本目录: %s", config->script_path);
    LOG_INFO("PTY功能: %s", config->enable_pty ? "启用" : "禁用");
    LOG_INFO("脚本执行: %s", config->enable_script ? "启用" : "禁用");
    LOG_INFO("SSL加密: %s", config->use_ssl ? "启用" : "禁用");
    if (config->use_ssl && config->ca_path[0] != '\0') {
        LOG_INFO("CA证书: %s", config->ca_path);
    }
    LOG_INFO("自动更新: %s", config->enable_auto_update ? "启用" : "禁用");
    LOG_INFO("==============================");
}