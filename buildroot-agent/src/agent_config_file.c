/*
 * 配置文件解析模块
 * 使用libconfig解析配置文件
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include "agent.h"
#include "libconfig.h"

/* 辅助函数：安全获取字符串值 */
static void safe_set_string(char *dest, size_t dest_size, const char *value)
{
    if (value && dest && dest_size > 0) {
        strncpy(dest, value, dest_size - 1);
        dest[dest_size - 1] = '\0';
    }
}

/* 辅助函数：从配置组获取字符串 */
static void get_group_string(config_setting_t *group, const char *name, 
                             char *dest, size_t dest_size, const char *default_val)
{
    const char *str = NULL;
    if (config_setting_lookup_string(group, name, &str) == CONFIG_TRUE) {
        safe_set_string(dest, dest_size, str);
    } else if (default_val) {
        safe_set_string(dest, dest_size, default_val);
    }
}

/* 辅助函数：从配置组获取整数 */
static int get_group_int(config_setting_t *group, const char *name, int default_val)
{
    int val;
    if (config_setting_lookup_int(group, name, &val) == CONFIG_TRUE) {
        return val;
    }
    return default_val;
}

/* 辅助函数：从配置组获取布尔值 */
static int get_group_bool(config_setting_t *group, const char *name, int default_val)
{
    int val;
    if (config_setting_lookup_bool(group, name, &val) == CONFIG_TRUE) {
        return val;
    }
    return default_val;
}

/* 加载libconfig配置文件 */
config_load_result_t config_load_yaml(agent_config_t *config, const char *path)
{
    config_t cfg;
    config_setting_t *root;
    
    if (!config || !path) return CONFIG_LOAD_PARSE_ERROR;
    
    config_set_defaults(config);
    
    config_init(&cfg);
    
    if (config_read_file(&cfg, path) == CONFIG_FALSE) {
        LOG_WARN("配置文件不存在或解析错误: %s (line %d: %s)", 
                 path, config_error_line(&cfg), config_error_text(&cfg));
        config_destroy(&cfg);
        return CONFIG_LOAD_NOT_FOUND;
    }
    
    root = config_root_setting(&cfg);
    
    /* server 配置 */
    config_setting_t *setting = config_setting_get_member(root, "server");
    if (setting) {
        get_group_string(setting, "addr", config->server_addr, 
                        sizeof(config->server_addr), DEFAULT_SERVER_ADDR);
        config->use_ssl = get_group_bool(setting, "use_ssl", 0);
        get_group_string(setting, "ca_path", config->ca_path, 
                        sizeof(config->ca_path), "");
    }
    
    /* device 配置 */
    setting = config_setting_get_member(root, "device");
    if (setting) {
        get_group_string(setting, "id", config->device_id, 
                        sizeof(config->device_id), "");
    }
    
    /* connection 配置 */
    setting = config_setting_get_member(root, "connection");
    if (setting) {
        config->heartbeat_interval = get_group_int(setting, "heartbeat_interval", 
                                                   DEFAULT_HEARTBEAT_SEC);
        config->reconnect_interval = get_group_int(setting, "reconnect_interval", 
                                                   DEFAULT_RECONNECT_SEC);
        config->status_interval = get_group_int(setting, "status_interval", 60);
    }
    
    /* paths 配置 */
    setting = config_setting_get_member(root, "paths");
    if (setting) {
        get_group_string(setting, "log", config->log_path, 
                        sizeof(config->log_path), DEFAULT_LOG_PATH);
        get_group_string(setting, "script", config->script_path, 
                        sizeof(config->script_path), DEFAULT_SCRIPT_PATH);
        get_group_string(setting, "update_temp", config->update_temp_path, 
                        sizeof(config->update_temp_path), DEFAULT_UPDATE_TEMP_PATH);
        get_group_string(setting, "update_backup", config->update_backup_path, 
                        sizeof(config->update_backup_path), DEFAULT_UPDATE_BACKUP_PATH);
    }
    
    /* features 配置 */
    setting = config_setting_get_member(root, "features");
    if (setting) {
        config->enable_pty = get_group_bool(setting, "pty", 1);
        config->enable_script = get_group_bool(setting, "script", 1);
        config->enable_auto_update = get_group_bool(setting, "auto_update", 0);
    }
    
    /* update 配置 */
    setting = config_setting_get_member(root, "update");
    if (setting) {
        config->update_check_interval = get_group_int(setting, "check_interval", 
                                                      DEFAULT_UPDATE_CHECK_INTERVAL);
        get_group_string(setting, "channel", config->update_channel, 
                        sizeof(config->update_channel), DEFAULT_UPDATE_CHANNEL);
        config->update_require_confirm = get_group_bool(setting, "require_confirm", 1);
        config->update_rollback_on_fail = get_group_bool(setting, "rollback_on_fail", 1);
        config->update_rollback_timeout = get_group_int(setting, "rollback_timeout", 
                                                        DEFAULT_UPDATE_ROLLBACK_TIMEOUT);
        config->update_verify_checksum = get_group_bool(setting, "verify_checksum", 1);
    }
    
    /* ping 配置 */
    setting = config_setting_get_member(root, "ping");
    if (setting) {
        config->enable_ping = get_group_bool(setting, "enable", 0);
        config->ping_interval = get_group_int(setting, "interval", 60);
        config->ping_timeout = get_group_int(setting, "timeout", 5);
        config->ping_count = get_group_int(setting, "count", 4);
        
        /* ping targets */
        config_setting_t *targets = config_setting_get_member(setting, "targets");
        if (targets && config_setting_is_list(targets)) {
            int count = config_setting_length(targets);
            if (count > 16) count = 16;
            
            config->ping_target_count = count;
            for (int i = 0; i < count; i++) {
                config_setting_t *target = config_setting_get_elem(targets, i);
                if (target) {
                    get_group_string(target, "ip", config->ping_targets[i].ip, 
                                    sizeof(config->ping_targets[i].ip), "");
                    get_group_string(target, "name", config->ping_targets[i].name, 
                                    sizeof(config->ping_targets[i].name), "");
                }
            }
        }
    }
    
    /* logging 配置 */
    setting = config_setting_get_member(root, "logging");
    if (setting) {
        const char *level = NULL;
        if (config_setting_lookup_string(setting, "level", &level) == CONFIG_TRUE) {
            if (strcmp(level, "debug") == 0) config->log_level = LOG_LEVEL_DEBUG;
            else if (strcmp(level, "info") == 0) config->log_level = LOG_LEVEL_INFO;
            else if (strcmp(level, "warn") == 0) config->log_level = LOG_LEVEL_WARN;
            else if (strcmp(level, "error") == 0) config->log_level = LOG_LEVEL_ERROR;
        }
    }
    
    /* twin 配置 */
    setting = config_setting_get_member(root, "twin");
    if (setting) {
        config->enable_twin = get_group_bool(setting, "enable", 0);
        get_group_string(setting, "mqtt_broker", config->mqtt_broker, 
                        sizeof(config->mqtt_broker), "localhost");
        config->mqtt_port = get_group_int(setting, "mqtt_port", 1883);
        get_group_string(setting, "mqtt_username", config->mqtt_username, 
                        sizeof(config->mqtt_username), "");
        get_group_string(setting, "mqtt_password", config->mqtt_password, 
                        sizeof(config->mqtt_password), "");
        config->twin_report_interval = get_group_int(setting, "report_interval", 30);
    }
    
    config_destroy(&cfg);
    
    config_validate(config);
    
    LOG_INFO("配置文件已加载: %s", path);
    return CONFIG_LOAD_OK;
}

/* 保存libconfig配置文件 */
int config_save_yaml(agent_config_t *config, const char *path)
{
    config_t cfg;
    config_setting_t *root, *group;
    
    if (!config || !path) return -1;
    
    config_init(&cfg);
    root = config_root_setting(&cfg);
    
    /* server 配置 */
    group = config_setting_add(root, "server", CONFIG_TYPE_GROUP);
    config_setting_set_string(config_setting_add(group, "addr", CONFIG_TYPE_STRING), 
                              config->server_addr);
    config_setting_set_bool(config_setting_add(group, "use_ssl", CONFIG_TYPE_BOOL), 
                            config->use_ssl);
    config_setting_set_string(config_setting_add(group, "ca_path", CONFIG_TYPE_STRING), 
                              config->ca_path);
    
    /* device 配置 */
    group = config_setting_add(root, "device", CONFIG_TYPE_GROUP);
    config_setting_set_string(config_setting_add(group, "id", CONFIG_TYPE_STRING), 
                              config->device_id);
    
    /* connection 配置 */
    group = config_setting_add(root, "connection", CONFIG_TYPE_GROUP);
    config_setting_set_int(config_setting_add(group, "heartbeat_interval", CONFIG_TYPE_INT), 
                           config->heartbeat_interval);
    config_setting_set_int(config_setting_add(group, "reconnect_interval", CONFIG_TYPE_INT), 
                           config->reconnect_interval);
    config_setting_set_int(config_setting_add(group, "status_interval", CONFIG_TYPE_INT), 
                           config->status_interval);
    
    /* paths 配置 */
    group = config_setting_add(root, "paths", CONFIG_TYPE_GROUP);
    config_setting_set_string(config_setting_add(group, "log", CONFIG_TYPE_STRING), 
                              config->log_path);
    config_setting_set_string(config_setting_add(group, "script", CONFIG_TYPE_STRING), 
                              config->script_path);
    config_setting_set_string(config_setting_add(group, "update_temp", CONFIG_TYPE_STRING), 
                              config->update_temp_path);
    config_setting_set_string(config_setting_add(group, "update_backup", CONFIG_TYPE_STRING), 
                              config->update_backup_path);
    
    /* features 配置 */
    group = config_setting_add(root, "features", CONFIG_TYPE_GROUP);
    config_setting_set_bool(config_setting_add(group, "pty", CONFIG_TYPE_BOOL), 
                            config->enable_pty);
    config_setting_set_bool(config_setting_add(group, "script", CONFIG_TYPE_BOOL), 
                            config->enable_script);
    config_setting_set_bool(config_setting_add(group, "auto_update", CONFIG_TYPE_BOOL), 
                            config->enable_auto_update);
    
    /* update 配置 */
    group = config_setting_add(root, "update", CONFIG_TYPE_GROUP);
    config_setting_set_int(config_setting_add(group, "check_interval", CONFIG_TYPE_INT), 
                           config->update_check_interval);
    config_setting_set_string(config_setting_add(group, "channel", CONFIG_TYPE_STRING), 
                              config->update_channel);
    config_setting_set_bool(config_setting_add(group, "require_confirm", CONFIG_TYPE_BOOL), 
                            config->update_require_confirm);
    config_setting_set_bool(config_setting_add(group, "rollback_on_fail", CONFIG_TYPE_BOOL), 
                            config->update_rollback_on_fail);
    config_setting_set_int(config_setting_add(group, "rollback_timeout", CONFIG_TYPE_INT), 
                           config->update_rollback_timeout);
    config_setting_set_bool(config_setting_add(group, "verify_checksum", CONFIG_TYPE_BOOL), 
                            config->update_verify_checksum);
    
    /* ping 配置 */
    group = config_setting_add(root, "ping", CONFIG_TYPE_GROUP);
    config_setting_set_bool(config_setting_add(group, "enable", CONFIG_TYPE_BOOL), 
                            config->enable_ping);
    config_setting_set_int(config_setting_add(group, "interval", CONFIG_TYPE_INT), 
                           config->ping_interval);
    config_setting_set_int(config_setting_add(group, "timeout", CONFIG_TYPE_INT), 
                           config->ping_timeout);
    config_setting_set_int(config_setting_add(group, "count", CONFIG_TYPE_INT), 
                           config->ping_count);
    
    /* ping targets */
    if (config->ping_target_count > 0) {
        config_setting_t *arr = config_setting_add(group, "targets", CONFIG_TYPE_LIST);
        int i;
        for (i = 0; i < config->ping_target_count; i++) {
            config_setting_t *setting = config_setting_add(arr, NULL, CONFIG_TYPE_GROUP);
            config_setting_set_string(config_setting_add(setting, "ip", CONFIG_TYPE_STRING), 
                                      config->ping_targets[i].ip);
            if (config->ping_targets[i].name[0] != '\0') {
                config_setting_set_string(config_setting_add(setting, "name", CONFIG_TYPE_STRING), 
                                          config->ping_targets[i].name);
            }
        }
    }
    
    /* logging 配置 */
    group = config_setting_add(root, "logging", CONFIG_TYPE_GROUP);
    const char *level_str = "info";
    switch (config->log_level) {
        case LOG_LEVEL_DEBUG: level_str = "debug"; break;
        case LOG_LEVEL_INFO: level_str = "info"; break;
        case LOG_LEVEL_WARN: level_str = "warn"; break;
        case LOG_LEVEL_ERROR: level_str = "error"; break;
    }
    config_setting_set_string(config_setting_add(group, "level", CONFIG_TYPE_STRING), 
                              level_str);
    
    /* twin 配置 */
    group = config_setting_add(root, "twin", CONFIG_TYPE_GROUP);
    config_setting_set_bool(config_setting_add(group, "enable", CONFIG_TYPE_BOOL), 
                            config->enable_twin);
    config_setting_set_string(config_setting_add(group, "mqtt_broker", CONFIG_TYPE_STRING), 
                              config->mqtt_broker);
    config_setting_set_int(config_setting_add(group, "mqtt_port", CONFIG_TYPE_INT), 
                           config->mqtt_port);
    config_setting_set_string(config_setting_add(group, "mqtt_username", CONFIG_TYPE_STRING), 
                              config->mqtt_username);
    config_setting_set_string(config_setting_add(group, "mqtt_password", CONFIG_TYPE_STRING), 
                              config->mqtt_password);
    config_setting_set_int(config_setting_add(group, "report_interval", CONFIG_TYPE_INT), 
                           config->twin_report_interval);
    
    /* 写入文件 */
    if (config_write_file(&cfg, path) == CONFIG_FALSE) {
        LOG_ERROR("无法写入配置文件: %s", path);
        config_destroy(&cfg);
        return -1;
    }
    
    config_destroy(&cfg);
    LOG_INFO("配置文件已保存: %s", path);
    return 0;
}