/*
 * YAML配置解析模块
 * 使用libyaml解析YAML格式配置文件
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <ctype.h>
#include "agent.h"

#include "yaml.h"

/* 解析上下文 */
typedef struct {
    agent_config_t *config;
    char current_section[64];
    char current_key[128];
    int in_targets;
    int expect_target_value;  /* 在targets模式下，等待处理value */
    int target_index;
    int target_field_count;
    int mapping_depth;
} yaml_parse_ctx_t;

/* 获取字符串值 */
static void get_string_value(yaml_event_t *event, char *dest, size_t dest_size)
{
    if (event->type == YAML_SCALAR_EVENT && event->data.scalar.value) {
        strncpy(dest, (const char *)event->data.scalar.value, dest_size - 1);
        dest[dest_size - 1] = '\0';
    }
}

/* 获取整数值 */
static int get_int_value(yaml_event_t *event, int default_val)
{
    if (event->type == YAML_SCALAR_EVENT && event->data.scalar.value) {
        return atoi((const char *)event->data.scalar.value);
    }
    return default_val;
}

/* 获取布尔值 */
static int get_bool_value(yaml_event_t *event, int default_val)
{
    if (event->type == YAML_SCALAR_EVENT && event->data.scalar.value) {
        const char *val = (const char *)event->data.scalar.value;
        if (strcmp(val, "true") == 0 || strcmp(val, "1") == 0 || 
            strcmp(val, "yes") == 0 || strcmp(val, "on") == 0) {
            return 1;
        }
        if (strcmp(val, "false") == 0 || strcmp(val, "0") == 0 || 
            strcmp(val, "no") == 0 || strcmp(val, "off") == 0) {
            return 0;
        }
    }
    return default_val;
}

/* 处理配置项 */
static void handle_config_key(yaml_parse_ctx_t *ctx, const char *key, yaml_event_t *event)
{
    agent_config_t *cfg = ctx->config;
    LOG_DEBUG("[YAML] handle_config_key: section='%s', key='%s'", ctx->current_section, key);
    
    /* server.* */
    if (strcmp(ctx->current_section, "server") == 0) {
        if (strcmp(key, "addr") == 0) {
            get_string_value(event, cfg->server_addr, sizeof(cfg->server_addr));
        } else if (strcmp(key, "use_ssl") == 0) {
            cfg->use_ssl = get_bool_value(event, 0);
        } else if (strcmp(key, "ca_path") == 0) {
            get_string_value(event, cfg->ca_path, sizeof(cfg->ca_path));
        }
    }
    /* device.* */
    else if (strcmp(ctx->current_section, "device") == 0) {
        if (strcmp(key, "id") == 0) {
            get_string_value(event, cfg->device_id, sizeof(cfg->device_id));
        }
    }
    /* connection.* */
    else if (strcmp(ctx->current_section, "connection") == 0) {
        if (strcmp(key, "heartbeat_interval") == 0) {
            cfg->heartbeat_interval = get_int_value(event, DEFAULT_HEARTBEAT_SEC);
        } else if (strcmp(key, "reconnect_interval") == 0) {
            cfg->reconnect_interval = get_int_value(event, DEFAULT_RECONNECT_SEC);
        } else if (strcmp(key, "status_interval") == 0) {
            cfg->status_interval = get_int_value(event, 60);
        }
    }
    /* paths.* */
    else if (strcmp(ctx->current_section, "paths") == 0) {
        if (strcmp(key, "log") == 0) {
            get_string_value(event, cfg->log_path, sizeof(cfg->log_path));
        } else if (strcmp(key, "script") == 0) {
            get_string_value(event, cfg->script_path, sizeof(cfg->script_path));
        } else if (strcmp(key, "update_temp") == 0) {
            get_string_value(event, cfg->update_temp_path, sizeof(cfg->update_temp_path));
        } else if (strcmp(key, "update_backup") == 0) {
            get_string_value(event, cfg->update_backup_path, sizeof(cfg->update_backup_path));
        }
    }
    /* features.* */
    else if (strcmp(ctx->current_section, "features") == 0) {
        if (strcmp(key, "pty") == 0) {
            cfg->enable_pty = get_bool_value(event, 1);
        } else if (strcmp(key, "script") == 0) {
            cfg->enable_script = get_bool_value(event, 1);
        } else if (strcmp(key, "auto_update") == 0) {
            cfg->enable_auto_update = get_bool_value(event, 0);
        }
    }
    /* update.* */
    else if (strcmp(ctx->current_section, "update") == 0) {
        if (strcmp(key, "check_interval") == 0) {
            cfg->update_check_interval = get_int_value(event, DEFAULT_UPDATE_CHECK_INTERVAL);
        } else if (strcmp(key, "channel") == 0) {
            get_string_value(event, cfg->update_channel, sizeof(cfg->update_channel));
        } else if (strcmp(key, "require_confirm") == 0) {
            cfg->update_require_confirm = get_bool_value(event, 1);
        } else if (strcmp(key, "rollback_on_fail") == 0) {
            cfg->update_rollback_on_fail = get_bool_value(event, 1);
        } else if (strcmp(key, "rollback_timeout") == 0) {
            cfg->update_rollback_timeout = get_int_value(event, DEFAULT_UPDATE_ROLLBACK_TIMEOUT);
        } else if (strcmp(key, "verify_checksum") == 0) {
            cfg->update_verify_checksum = get_bool_value(event, 1);
        }
    }
    /* ping.* */
    else if (strcmp(ctx->current_section, "ping") == 0) {
        if (strcmp(key, "enable") == 0) {
            cfg->enable_ping = get_bool_value(event, 0);
        } else if (strcmp(key, "interval") == 0) {
            cfg->ping_interval = get_int_value(event, 60);
        } else if (strcmp(key, "timeout") == 0) {
            cfg->ping_timeout = get_int_value(event, 5);
        } else if (strcmp(key, "count") == 0) {
            cfg->ping_count = get_int_value(event, 4);
        }
    }
    /* logging.* */
    else if (strcmp(ctx->current_section, "logging") == 0) {
        if (strcmp(key, "level") == 0) {
            char level[32];
            get_string_value(event, level, sizeof(level));
            if (strcmp(level, "debug") == 0) cfg->log_level = LOG_LEVEL_DEBUG;
            else if (strcmp(level, "info") == 0) cfg->log_level = LOG_LEVEL_INFO;
            else if (strcmp(level, "warn") == 0) cfg->log_level = LOG_LEVEL_WARN;
            else if (strcmp(level, "error") == 0) cfg->log_level = LOG_LEVEL_ERROR;
        }
    }
}

/* 处理Ping目标项 */
static void handle_ping_target(yaml_parse_ctx_t *ctx, const char *key, yaml_event_t *event)
{
    agent_config_t *cfg = ctx->config;
    
    if (ctx->target_index >= 16) return;
    
    ping_target_t *target = &cfg->ping_targets[ctx->target_index];
    
    if (strcmp(key, "ip") == 0) {
        get_string_value(event, target->ip, sizeof(target->ip));
    } else if (strcmp(key, "name") == 0) {
        get_string_value(event, target->name, sizeof(target->name));
    }
}

/* 解析YAML文档 */
static int parse_yaml_document(yaml_parser_t *parser, yaml_parse_ctx_t *ctx)
{
    yaml_event_t event;
    int done = 0;
    char current_key[128] = {0};
    
    while (!done) {
        if (!yaml_parser_parse(parser, &event)) {
            LOG_ERROR("YAML解析错误: %s", parser->problem);
            return -1;
        }
        
        switch (event.type) {
            case YAML_STREAM_START_EVENT:
            case YAML_DOCUMENT_START_EVENT:
                break;
                
            case YAML_DOCUMENT_END_EVENT:
            case YAML_STREAM_END_EVENT:
                done = (event.type == YAML_STREAM_END_EVENT);
                break;
            case YAML_MAPPING_START_EVENT:
                ctx->mapping_depth++;
                if (ctx->in_targets) {
                    /* Ping target mapping开始 - 重置key状态 */
                    ctx->target_field_count = 0;
                    ctx->expect_target_value = 0;
                    current_key[0] = '\0';
                }
                break;
            case YAML_MAPPING_END_EVENT:
                if (ctx->in_targets && ctx->target_field_count > 0) {
                    /* Ping target mapping结束 */
                    ctx->target_index++;
                    ctx->target_field_count = 0;
                }
                if (ctx->in_targets) {
                    /* 重置key状态，为下一个target准备 */
                    ctx->expect_target_value = 0;
                    current_key[0] = '\0';
                }
                ctx->mapping_depth--;
                /* 注意：不在这里清空current_section或in_targets */
                break;
                
            case YAML_SEQUENCE_START_EVENT:
                if (strcmp(ctx->current_section, "ping") == 0 && 
                    strcmp(current_key, "targets") == 0) {
                    ctx->in_targets = 1;
                    ctx->target_index = 0;
                    ctx->target_field_count = 0;
                }
                break;
            case YAML_SEQUENCE_END_EVENT:
                if (ctx->in_targets) {
                    /* Ping targets序列结束，设置target数量 */
                    ctx->config->ping_target_count = ctx->target_index;
                }
                ctx->in_targets = 0;
                ctx->expect_target_value = 0;
                ctx->target_index = 0;
                /* 清除section，回到顶层等待新的section */
                ctx->current_section[0] = '\0';
                current_key[0] = '\0';
                break;
                
            case YAML_SCALAR_EVENT:
                if (ctx->mapping_depth > 0 && !ctx->in_targets) {
                    /* 这是一个key */
                    if (current_key[0] != '\0') {
                        /* 前面有key，现在处理value */
                        handle_config_key(ctx, current_key, &event);
                        current_key[0] = '\0';
                    } else {
                        /* 新的key */
                        if (event.data.scalar.value) {
                            strncpy(current_key, (const char *)event.data.scalar.value, sizeof(current_key) - 1);
                            
                            /* 检查是否是section - 只在mapping_depth=1时检查（顶层key） */
                            if (ctx->mapping_depth == 1) {
                                if (strcmp(current_key, "server") == 0 ||
                                    strcmp(current_key, "device") == 0 ||
                                    strcmp(current_key, "connection") == 0 ||
                                    strcmp(current_key, "paths") == 0 ||
                                    strcmp(current_key, "features") == 0 ||
                                    strcmp(current_key, "update") == 0 ||
                                    strcmp(current_key, "ping") == 0 ||
                                    strcmp(current_key, "logging") == 0) {
                                    strncpy(ctx->current_section, current_key, sizeof(ctx->current_section) - 1);
                                    current_key[0] = '\0';
                                }
                            }
                        }
                    }
                } else if (ctx->in_targets) {
                    /* Ping目标内的key-value */
                    if (ctx->expect_target_value) {
                        /* 前一个scalar是key，现在这个是value */
                        handle_ping_target(ctx, current_key, &event);
                        current_key[0] = '\0';
                        ctx->expect_target_value = 0;
                        ctx->target_field_count++;
                    } else if (current_key[0] != '\0') {
                        /* 已经有key但没有设置expect，说明可能跳过了某些内容 */
                        ctx->expect_target_value = 1;
                    } else if (event.data.scalar.value) {
                        /* 跳过列表项标记 '-' 和空值 */
                        const char *val = (const char *)event.data.scalar.value;
                        if (val[0] != '-' && val[0] != '\0') {
                            strncpy(current_key, val, sizeof(current_key) - 1);
                            ctx->expect_target_value = 1;
                        }
                    }
                }
                break;
                
            default:
                break;
        }
        
        yaml_event_delete(&event);
    }
    
    return 0;
}

/* 加载YAML配置文件 */
config_load_result_t config_load_yaml(agent_config_t *config, const char *path)
{
    yaml_parser_t parser;
    yaml_parse_ctx_t ctx;
    FILE *fp;
    int result;
    
    if (!config || !path) return CONFIG_LOAD_PARSE_ERROR;
    
    fp = fopen(path, "r");
    if (!fp) {
        LOG_WARN("配置文件不存在: %s", path);
        return CONFIG_LOAD_NOT_FOUND;
    }
    
    /* 初始化解析器 */
    if (!yaml_parser_initialize(&parser)) {
        LOG_ERROR("无法初始化YAML解析器");
        fclose(fp);
        return CONFIG_LOAD_PARSE_ERROR;
    }
    
    yaml_parser_set_input_file(&parser, fp);
    
    /* 初始化解析上下文 */
    memset(&ctx, 0, sizeof(ctx));
    ctx.config = config;
    
    /* 解析文档 */
    result = parse_yaml_document(&parser, &ctx);
    
    /* 清理 */
    yaml_parser_delete(&parser);
    fclose(fp);
    
    if (result != 0) {
        return CONFIG_LOAD_PARSE_ERROR;
    }
    
    /* 验证并修正配置 */
    config_validate(config);
    
    LOG_INFO("YAML配置文件已加载: %s", path);
    return CONFIG_LOAD_OK;
}

/* 保存YAML配置文件 */
int config_save_yaml(agent_config_t *config, const char *path)
{
    FILE *fp;
    int i;
    
    if (!config || !path) return -1;
    
    fp = fopen(path, "w");
    if (!fp) {
        LOG_ERROR("无法创建配置文件: %s (%s)", path, strerror(errno));
        return -1;
    }
    
    fprintf(fp, "# Buildroot Agent Configuration (YAML)\n");
    fprintf(fp, "# \n");
    fprintf(fp, "# 使用说明：\n");
    fprintf(fp, "# 1. 根据实际情况修改配置项\n");
    fprintf(fp, "# 2. 运行 agent: ./buildroot-agent -c ./agent.yaml\n");
    fprintf(fp, "# \n");
    
    fprintf(fp, "server:\n");
    fprintf(fp, "  addr: \"%s\"\n", config->server_addr);
    fprintf(fp, "  use_ssl: %s\n", config->use_ssl ? "true" : "false");
    fprintf(fp, "  ca_path: \"%s\"\n", config->ca_path);
    
    fprintf(fp, "\ndevice:\n");
    fprintf(fp, "  id: \"%s\"\n", config->device_id);
    
    fprintf(fp, "\nconnection:\n");
    fprintf(fp, "  heartbeat_interval: %d\n", config->heartbeat_interval);
    fprintf(fp, "  reconnect_interval: %d\n", config->reconnect_interval);
    fprintf(fp, "  status_interval: %d\n", config->status_interval);
    
    fprintf(fp, "\npaths:\n");
    fprintf(fp, "  log: \"%s\"\n", config->log_path);
    fprintf(fp, "  script: \"%s\"\n", config->script_path);
    fprintf(fp, "  update_temp: \"%s\"\n", config->update_temp_path);
    fprintf(fp, "  update_backup: \"%s\"\n", config->update_backup_path);
    
    fprintf(fp, "\nfeatures:\n");
    fprintf(fp, "  pty: %s\n", config->enable_pty ? "true" : "false");
    fprintf(fp, "  script: %s\n", config->enable_script ? "true" : "false");
    fprintf(fp, "  auto_update: %s\n", config->enable_auto_update ? "true" : "false");
    
    fprintf(fp, "\nupdate:\n");
    fprintf(fp, "  check_interval: %d\n", config->update_check_interval);
    fprintf(fp, "  channel: \"%s\"\n", config->update_channel);
    fprintf(fp, "  require_confirm: %s\n", config->update_require_confirm ? "true" : "false");
    fprintf(fp, "  rollback_on_fail: %s\n", config->update_rollback_on_fail ? "true" : "false");
    fprintf(fp, "  rollback_timeout: %d\n", config->update_rollback_timeout);
    fprintf(fp, "  verify_checksum: %s\n", config->update_verify_checksum ? "true" : "false");
    
    fprintf(fp, "\nping:\n");
    fprintf(fp, "  enable: %s\n", config->enable_ping ? "true" : "false");
    fprintf(fp, "  interval: %d\n", config->ping_interval);
    fprintf(fp, "  timeout: %d\n", config->ping_timeout);
    fprintf(fp, "  count: %d\n", config->ping_count);
    
    if (config->ping_target_count > 0) {
        fprintf(fp, "  targets:\n");
        for (i = 0; i < config->ping_target_count; i++) {
            fprintf(fp, "    - ip: \"%s\"\n", config->ping_targets[i].ip);
            if (config->ping_targets[i].name[0] != '\0') {
                fprintf(fp, "      name: \"%s\"\n", config->ping_targets[i].name);
            }
        }
    }
    
    fprintf(fp, "\nlogging:\n");
    fprintf(fp, "  level: \"%s\"\n", 
        config->log_level == LOG_LEVEL_DEBUG ? "debug" :
        config->log_level == LOG_LEVEL_INFO ? "info" :
        config->log_level == LOG_LEVEL_WARN ? "warn" : "error");
    
    fclose(fp);
    
    LOG_INFO("YAML配置文件已保存: %s", path);
    return 0;
}
