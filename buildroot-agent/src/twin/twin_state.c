/**
 * @file twin_state.c
 * @brief Device Twin 状态管理模块实现
 */

#include "twin/twin_state.h"
#include "twin/twin_diff.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>

/* cJSON 库 - 需要链接或包含 */
#include <cjson/cJSON.h>

/* ==================== 内部常量 ==================== */

#define TWIN_STATE_FILE_VERSION  1
#define TWIN_MAX_FILE_SIZE       (1024 * 1024)  /* 1MB */

/* ==================== 内部函数声明 ==================== */

static int write_file_atomic(const char* filepath, const char* content, size_t len);

/* ==================== 公开函数实现 ==================== */

int twin_state_init(twin_state_t* state, const char* device_id) {
    if (!state || !device_id) {
        return -1;
    }
    
    /* 清零 */
    memset(state, 0, sizeof(twin_state_t));
    
    /* 复制设备 ID */
    size_t id_len = strlen(device_id);
    if (id_len >= sizeof(state->device_id)) {
        return -1;  /* ID 过长 */
    }
    memcpy(state->device_id, device_id, id_len + 1);
    
    /* 创建空的 JSON 对象 */
    state->desired = cJSON_CreateObject();
    state->reported = cJSON_CreateObject();
    state->delta = cJSON_CreateObject();
    
    if (!state->desired || !state->reported || !state->delta) {
        twin_state_destroy(state);
        return -1;
    }
    
    state->desired_version = 0;
    state->reported_version = 0;
    state->desired_time = 0;
    state->reported_time = 0;
    state->sync_in_progress = false;
    state->pending_changes = false;
    state->initialized = true;
    state->persist_path = NULL;
    
    return 0;
}

void twin_state_destroy(twin_state_t* state) {
    if (!state) {
        return;
    }
    
    if (state->desired) {
        cJSON_Delete(state->desired);
        state->desired = NULL;
    }
    
    if (state->reported) {
        cJSON_Delete(state->reported);
        state->reported = NULL;
    }
    
    if (state->delta) {
        cJSON_Delete(state->delta);
        state->delta = NULL;
    }
    
    if (state->persist_path) {
        free(state->persist_path);
        state->persist_path = NULL;
    }
    
    state->initialized = false;
}

int twin_state_set_desired(twin_state_t* state, cJSON* desired, twin_version_t version) {
    if (!state || !state->initialized || !desired) {
        return -1;
    }
    
    /* 版本检查：忽略旧版本 */
    if (version <= state->desired_version) {
        return 1;  /* 忽略 */
    }
    
    /* 替换 desired */
    cJSON* new_desired = cJSON_Duplicate(desired, 1);
    if (!new_desired) {
        return -1;
    }
    
    if (state->desired) {
        cJSON_Delete(state->desired);
    }
    state->desired = new_desired;
    state->desired_version = version;
    state->desired_time = twin_state_get_timestamp();
    
    /* 重新计算 delta */
    twin_state_recalculate_delta(state);
    
    /* 触发回调 */
    if (state->on_desired_received) {
        state->on_desired_received(state, state->desired);
    }
    
    if (state->on_delta_changed && cJSON_GetArraySize(state->delta) > 0) {
        state->on_delta_changed(state, state->delta);
    }
    
    return 0;
}

int twin_state_update_reported(twin_state_t* state, cJSON* partial) {
    if (!state || !state->initialized || !partial) {
        return -1;
    }
    
    /* 遍历 partial，合并到 reported */
    cJSON* item = NULL;
    cJSON_ArrayForEach(item, partial) {
        const char* key = item->string;
        
        /* 删除旧值 */
        cJSON_DeleteItemFromObject(state->reported, key);
        
        /* 添加新值 */
        cJSON* new_item = cJSON_Duplicate(item, 1);
        if (new_item) {
            cJSON_AddItemToObject(state->reported, key, new_item);
        }
    }
    
    state->reported_version++;
    state->reported_time = twin_state_get_timestamp();
    state->pending_changes = true;
    
    /* 重新计算 delta */
    twin_state_recalculate_delta(state);
    
    return 0;
}

int twin_state_set_reported(twin_state_t* state, cJSON* reported, twin_version_t version) {
    if (!state || !state->initialized || !reported) {
        return -1;
    }
    
    /* 版本检查 */
    if (version < state->reported_version) {
        version = state->reported_version + 1;
    }
    
    /* 替换 reported */
    cJSON* new_reported = cJSON_Duplicate(reported, 1);
    if (!new_reported) {
        return -1;
    }
    
    if (state->reported) {
        cJSON_Delete(state->reported);
    }
    state->reported = new_reported;
    state->reported_version = version;
    state->reported_time = twin_state_get_timestamp();
    state->pending_changes = true;
    
    /* 重新计算 delta */
    twin_state_recalculate_delta(state);
    
    return 0;
}

int twin_state_recalculate_delta(twin_state_t* state) {
    if (!state || !state->initialized) {
        return -1;
    }
    
    /* 计算差异 */
    cJSON* new_delta = twin_diff_compute(state->desired, state->reported);
    
    if (state->delta) {
        cJSON_Delete(state->delta);
    }
    state->delta = new_delta;
    
    return 0;
}

cJSON* twin_state_get_delta(const twin_state_t* state) {
    if (!state || !state->initialized) {
        return NULL;
    }
    return state->delta;
}

bool twin_state_has_pending_changes(const twin_state_t* state) {
    if (!state || !state->initialized) {
        return false;
    }
    return state->pending_changes;
}

bool twin_state_is_synced(const twin_state_t* state) {
    if (!state || !state->initialized) {
        return false;
    }
    return cJSON_GetArraySize(state->delta) == 0;
}

cJSON* twin_state_get_desired_field(const twin_state_t* state, const char* path) {
    if (!state || !state->initialized || !path) {
        return NULL;
    }
    
    /* 解析路径 (如 "config.sampleRate") */
    cJSON* current = state->desired;
    char* path_copy = strdup(path);
    char* token = strtok(path_copy, ".");
    
    while (token && current) {
        if (cJSON_IsObject(current)) {
            current = cJSON_GetObjectItem(current, token);
        } else {
            current = NULL;
        }
        token = strtok(NULL, ".");
    }
    
    free(path_copy);
    return current;
}

cJSON* twin_state_get_reported_field(const twin_state_t* state, const char* path) {
    if (!state || !state->initialized || !path) {
        return NULL;
    }
    
    cJSON* current = state->reported;
    char* path_copy = strdup(path);
    char* token = strtok(path_copy, ".");
    
    while (token && current) {
        if (cJSON_IsObject(current)) {
            current = cJSON_GetObjectItem(current, token);
        } else {
            current = NULL;
        }
        token = strtok(NULL, ".");
    }
    
    free(path_copy);
    return current;
}

int twin_state_load(twin_state_t* state, const char* filepath) {
    if (!state || !state->initialized || !filepath) {
        return -1;
    }
    
    /* 检查文件是否存在 */
    if (access(filepath, R_OK) != 0) {
        return 1;  /* 文件不存在 */
    }
    
    /* 读取文件 */
    FILE* fp = fopen(filepath, "r");
    if (!fp) {
        return -1;
    }
    
    /* 获取文件大小 */
    fseek(fp, 0, SEEK_END);
    long file_size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    if (file_size <= 0 || file_size > TWIN_MAX_FILE_SIZE) {
        fclose(fp);
        return -1;
    }
    
    /* 分配缓冲区 */
    char* buffer = (char*)malloc(file_size + 1);
    if (!buffer) {
        fclose(fp);
        return -1;
    }
    
    /* 读取内容 */
    size_t read_size = fread(buffer, 1, file_size, fp);
    fclose(fp);
    
    if (read_size != (size_t)file_size) {
        free(buffer);
        return -1;
    }
    buffer[file_size] = '\0';
    
    /* 解析 JSON */
    cJSON* root = cJSON_Parse(buffer);
    free(buffer);
    
    if (!root) {
        return -1;
    }
    
    /* 提取字段 */
    cJSON* device_id = cJSON_GetObjectItem(root, "deviceId");
    cJSON* desired_obj = cJSON_GetObjectItem(root, "desired");
    cJSON* reported_obj = cJSON_GetObjectItem(root, "reported");
    
    if (!device_id || !cJSON_IsString(device_id)) {
        cJSON_Delete(root);
        return -1;
    }
    
    /* 验证设备 ID */
    if (strcmp(device_id->valuestring, state->device_id) != 0) {
        cJSON_Delete(root);
        return -1;
    }
    
    /* 更新状态 */
    if (desired_obj && cJSON_IsObject(desired_obj)) {
        cJSON* version_obj = cJSON_GetObjectItem(desired_obj, "version");
        cJSON* data_obj = cJSON_GetObjectItem(desired_obj, "data");
        
        if (version_obj && data_obj) {
            twin_version_t version = (twin_version_t)version_obj->valueint;
            twin_state_set_desired(state, data_obj, version);
        }
    }
    
    if (reported_obj && cJSON_IsObject(reported_obj)) {
        cJSON* version_obj = cJSON_GetObjectItem(reported_obj, "version");
        cJSON* data_obj = cJSON_GetObjectItem(reported_obj, "data");
        
        if (version_obj && data_obj) {
            twin_version_t version = (twin_version_t)version_obj->valueint;
            twin_state_set_reported(state, data_obj, version);
        }
    }
    
    cJSON_Delete(root);
    
    /* 保存路径 */
    if (state->persist_path) {
        free(state->persist_path);
    }
    state->persist_path = strdup(filepath);
    
    return 0;
}

int twin_state_save(const twin_state_t* state, const char* filepath) {
    if (!state || !state->initialized) {
        return -1;
    }
    
    const char* path = filepath ? filepath : state->persist_path;
    if (!path) {
        return -1;
    }
    
    /* 构建 JSON */
    cJSON* root = cJSON_CreateObject();
    cJSON_AddNumberToObject(root, "version", TWIN_STATE_FILE_VERSION);
    cJSON_AddStringToObject(root, "deviceId", state->device_id);
    
    /* desired */
    cJSON* desired_obj = cJSON_CreateObject();
    cJSON_AddNumberToObject(desired_obj, "version", state->desired_version);
    cJSON_AddItemReferenceToObject(desired_obj, "data", state->desired);
    cJSON_AddItemToObject(root, "desired", desired_obj);
    
    /* reported */
    cJSON* reported_obj = cJSON_CreateObject();
    cJSON_AddNumberToObject(reported_obj, "version", state->reported_version);
    cJSON_AddItemReferenceToObject(reported_obj, "data", state->reported);
    cJSON_AddItemToObject(root, "reported", reported_obj);
    
    /* pending (待处理的 delta) */
    if (cJSON_GetArraySize(state->delta) > 0) {
        cJSON_AddItemReferenceToObject(root, "pending", state->delta);
    }
    
    /* 序列化 */
    char* json_str = cJSON_Print(root);
    cJSON_Delete(root);
    
    if (!json_str) {
        return -1;
    }
    
    /* 原子写入 */
    size_t len = strlen(json_str);
    int ret = write_file_atomic(path, json_str, len);
    free(json_str);
    
    return ret;
}

twin_timestamp_t twin_state_get_timestamp(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_REALTIME, &ts) != 0) {
        return 0;
    }
    return (twin_timestamp_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

void twin_state_print(const twin_state_t* state) {
    if (!state || !state->initialized) {
        printf("[Twin] Not initialized\n");
        return;
    }
    
    printf("[Twin] Device: %s\n", state->device_id);
    printf("[Twin] Desired version: %llu\n", (unsigned long long)state->desired_version);
    printf("[Twin] Reported version: %llu\n", (unsigned long long)state->reported_version);
    printf("[Twin] Synced: %s\n", twin_state_is_synced(state) ? "yes" : "no");
    
    char* desired_str = cJSON_Print(state->desired);
    char* reported_str = cJSON_Print(state->reported);
    char* delta_str = cJSON_Print(state->delta);
    
    printf("[Twin] Desired: %s\n", desired_str ? desired_str : "null");
    printf("[Twin] Reported: %s\n", reported_str ? reported_str : "null");
    printf("[Twin] Delta: %s\n", delta_str ? delta_str : "null");
    
    if (desired_str) free(desired_str);
    if (reported_str) free(reported_str);
    if (delta_str) free(delta_str);
}

/* ==================== 内部函数实现 ==================== */

static int write_file_atomic(const char* filepath, const char* content, size_t len) {
    /* 创建临时文件路径 */
    size_t path_len = strlen(filepath);
    char* tmp_path = (char*)malloc(path_len + 8);
    if (!tmp_path) {
        return -1;
    }
    snprintf(tmp_path, path_len + 8, "%s.tmp", filepath);
    
    /* 写入临时文件 */
    FILE* fp = fopen(tmp_path, "w");
    if (!fp) {
        free(tmp_path);
        return -1;
    }
    
    size_t written = fwrite(content, 1, len, fp);
    fflush(fp);
    fsync(fileno(fp));
    fclose(fp);
    
    if (written != len) {
        unlink(tmp_path);
        free(tmp_path);
        return -1;
    }
    
    /* 原子重命名 */
    if (rename(tmp_path, filepath) != 0) {
        unlink(tmp_path);
        free(tmp_path);
        return -1;
    }
    
    free(tmp_path);
    return 0;
}