/*
 * agent_update.c - 更新管理模块
 */

#include "agent.h"
#include "agent_json.h"
#include "cJSON.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>

#define SHA256_DIGEST_LENGTH 32

/* 全局变量 */
static update_status_t g_update_status = UPDATE_STATUS_IDLE;
pthread_mutex_t g_update_lock = PTHREAD_MUTEX_INITIALIZER;
update_info_t g_update_info;
bool g_update_thread_running = false;

/* 内部函数 */
static int parse_version(const char *version_str, int *major, int *minor, int *patch);
static int compare_versions(const char *v1, const char *v2);
static char *get_current_binary_path(void);
static int create_backup(const char *backup_path, char *backup_file);
static int extract_update_package(const char *package_path, const char *output_dir);
static int install_new_binary(const char *new_binary_path);
static int verify_installation(void);
static int send_update_progress(agent_context_t *ctx, int progress, const char *message);

/* 进度回调 */
void download_progress_callback(const char *url, int progress, int64_t downloaded, int64_t total_size, void *user_data)
{
    agent_context_t *ctx = (agent_context_t *)user_data;
    if (ctx) {
        char message[256];
        snprintf(message, sizeof(message), "下载中 %lld/%lld bytes (%d%%)",
                 (long long)downloaded, (long long)total_size, progress);
        send_update_progress(ctx, progress, message);
    }
}

/* 解析版本字符串 */
static int parse_version(const char *version_str, int *major, int *minor, int *patch)
{
    if (!version_str) return -1;
    
    int rc = sscanf(version_str, "%d.%d.%d", major, minor, patch);
    if (rc != 3) {
        LOG_ERROR("无效的版本格式: %s", version_str);
        return -1;
    }
    
    return 0;
}

/* 比较版本：返回 -1(v1<v2), 0(v1==v2), 1(v1>v2) */
static int compare_versions(const char *v1, const char *v2)
{
    int m1, n1, p1;
    int m2, n2, p2;
    
    if (parse_version(v1, &m1, &n1, &p1) != 0) return 0;
    if (parse_version(v2, &m2, &n2, &p2) != 0) return 0;
    
    if (m1 != m2) return m1 < m2 ? -1 : 1;
    if (n1 != n2) return n1 < n2 ? -1 : 1;
    if (p1 != p2) return p1 < p2 ? -1 : 1;
    
    return 0;
}

/* 发送更新进度 */
static int send_update_progress(agent_context_t *ctx, int progress, const char *message)
{
    if (!ctx) return -1;
    
    cJSON *root = cJSON_CreateObject();
    cJSON_AddNumberToObject(root, "progress", progress);
    cJSON_AddStringToObject(root, "message", message ? message : "");
    cJSON_AddStringToObject(root, "status", "downloading");
    char *json = cJSON_Print(root);
    cJSON_Delete(root);
    
    if (!json) {
        LOG_ERROR("JSON生成失败");
        return -1;
    }
    
    int rc = socket_send_json(ctx, MSG_TYPE_UPDATE_PROGRESS, json);
    free(json);
    
    return rc;
}

/* 检查更新 */
int update_check_version(agent_context_t *ctx)
{
    if (!ctx) return -1;
    
    LOG_INFO("检查更新，当前版本: %s, 渠道: %s",
             AGENT_VERSION, ctx->config.update_channel);
    
    /* 构建检查请求JSON */
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "device_id", ctx->config.device_id);
    cJSON_AddStringToObject(root, "current_version", AGENT_VERSION);
    cJSON_AddStringToObject(root, "channel", ctx->config.update_channel);
    char *json = cJSON_Print(root);
    cJSON_Delete(root);
    
    if (!json) {
        LOG_ERROR("JSON生成失败");
        return -1;
    }
    
    /* 发送检查请求到服务器 */
    int rc = socket_send_json(ctx, MSG_TYPE_UPDATE_CHECK, json);
    free(json);
    
    if (rc != 0) {
        LOG_ERROR("发送更新检查请求失败");
        return -1;
    }
    
    pthread_mutex_lock(&g_update_lock);
    g_update_status = UPDATE_STATUS_CHECKING;
    pthread_mutex_unlock(&g_update_lock);
    
    /* 服务器将返回 MSG_TYPE_UPDATE_INFO 消息 */
    /* 这部分在 protocol_handle_message 中处理 */
    
    return 0;
}

/* 下载更新包 */
int update_download_package(const char *url, const char *output_path, progress_callback_t callback, void *user_data)
{
    LOG_INFO("开始TCP下载更新包: %s", url);
    
    pthread_mutex_lock(&g_update_lock);
    g_update_status = UPDATE_STATUS_DOWNLOADING;
    pthread_mutex_unlock(&g_update_lock);
    
    tcp_download_config_t config;
    memset(&config, 0, sizeof(tcp_download_config_t));
    strncpy(config.file_path, url, sizeof(config.file_path) - 1);
    config.file_path[sizeof(config.file_path) - 1] = '\0';
    strncpy(config.output_path, output_path, sizeof(config.output_path) - 1);
    config.output_path[sizeof(config.output_path) - 1] = '\0';
    config.timeout = DEFAULT_DOWNLOAD_TIMEOUT;
    config.chunk_size = 32768;      /* 32KB块大小 */
    config.max_retries = 3;
    config.callback = callback;
    config.user_data = user_data;
    
    /* 执行TCP下载 */
    return tcp_download_file(g_agent_ctx, url, output_path, &config);
}

/* 后台下载和安装线程 */
void *update_download_and_install_thread(void *arg)
{
    typedef struct {
        char download_url[512];
        char download_path[512];
        char sha256_checksum[65];
        char request_id[64];
    } download_task_t;

    download_task_t *task = (download_task_t *)arg;
    if (!task) {
        LOG_ERROR("下载任务为空");
        return NULL;
    }

    /* 设置线程运行标志 */
    pthread_mutex_lock(&g_update_lock);
    g_update_thread_running = true;
    pthread_mutex_unlock(&g_update_lock);

    LOG_INFO("后台下载线程启动: %s (request_id=%s)", task->download_url, task->request_id);

    /* 执行下载 */
    int rc = update_download_package(
        task->download_url,
        task->download_path,
        download_progress_callback,
        g_agent_ctx
    );

    if (rc != 0) {
        LOG_ERROR("下载失败: %s", task->download_url);

        /* 发送错误通知 */
        cJSON *error_root = cJSON_CreateObject();
        cJSON_AddStringToObject(error_root, "status", "failed");
        cJSON_AddStringToObject(error_root, "error", "download_failed");
        cJSON_AddStringToObject(error_root, "request_id", task->request_id);
        char *error_json = cJSON_Print(error_root);
        cJSON_Delete(error_root);
        
        if (error_json) {
            socket_send_json(g_agent_ctx, MSG_TYPE_UPDATE_ERROR, error_json);
            free(error_json);
        }
        free(task);

        /* 清除线程运行标志 */
        pthread_mutex_lock(&g_update_lock);
        g_update_thread_running = false;
        pthread_mutex_unlock(&g_update_lock);

        return NULL;
    }

    LOG_INFO("下载完成，开始校验: %s", task->download_path);

    /* 发送进度：下载完成 */
    cJSON *progress_root = cJSON_CreateObject();
    cJSON_AddStringToObject(progress_root, "status", "downloaded");
    cJSON_AddStringToObject(progress_root, "request_id", task->request_id);
    cJSON_AddNumberToObject(progress_root, "progress", 100);
    char *progress_json = cJSON_Print(progress_root);
    cJSON_Delete(progress_root);
    
    if (progress_json) {
        socket_send_json(g_agent_ctx, MSG_TYPE_UPDATE_PROGRESS, progress_json);
        free(progress_json);
    }

    /* 校验文件 */
    LOG_INFO("开始校验文件: SHA256=%s",
             task->sha256_checksum[0] ? task->sha256_checksum : "(none)");

    if (!tcp_verify_checksum(task->download_path, task->sha256_checksum[0] ? task->sha256_checksum : NULL)) {
        LOG_ERROR("文件校验失败");

        /* 发送校验失败通知 */
        cJSON *error_root = cJSON_CreateObject();
        cJSON_AddStringToObject(error_root, "status", "verify_failed");
        cJSON_AddStringToObject(error_root, "request_id", task->request_id);
        cJSON_AddStringToObject(error_root, "error", "checksum_mismatch");
        char *error_json = cJSON_Print(error_root);
        cJSON_Delete(error_root);
        
        if (error_json) {
            socket_send_json(g_agent_ctx, MSG_TYPE_UPDATE_ERROR, error_json);
            free(error_json);
        }
        free(task);

        /* 清除线程运行标志 */
        pthread_mutex_lock(&g_update_lock);
        g_update_thread_running = false;
        pthread_mutex_unlock(&g_update_lock);

        return NULL;
    }

    LOG_INFO("文件校验通过");

    /* 发送校验成功通知 */
    cJSON *verify_root = cJSON_CreateObject();
    cJSON_AddStringToObject(verify_root, "status", "verified");
    cJSON_AddStringToObject(verify_root, "request_id", task->request_id);
    cJSON_AddStringToObject(verify_root, "path", task->download_path);
    char *verify_json = cJSON_Print(verify_root);
    cJSON_Delete(verify_root);
    
    if (verify_json) {
        socket_send_json(g_agent_ctx, MSG_TYPE_UPDATE_PROGRESS, verify_json);
        free(verify_json);
    }

    /* 发送安装通知 */
    cJSON *install_root = cJSON_CreateObject();
    cJSON_AddStringToObject(install_root, "status", "installing");
    cJSON_AddStringToObject(install_root, "request_id", task->request_id);
    cJSON_AddStringToObject(install_root, "path", task->download_path);
    char *install_json = cJSON_Print(install_root);
    cJSON_Delete(install_root);
    
    if (install_json) {
        socket_send_json(g_agent_ctx, MSG_TYPE_UPDATE_PROGRESS, install_json);
        free(install_json);
    }

    /* 开始安装 */
    LOG_INFO("开始安装更新包: %s", task->download_path);
    int install_rc = update_install_package(task->download_path);
    if (install_rc != 0) {
        LOG_ERROR("安装失败: %d", install_rc);
        /* 错误通知已在update_install_package内部发送 */
    } else {
        LOG_INFO("安装成功，准备重启...");

        /* 发送完成通知给服务器 */
        cJSON *complete_root = cJSON_CreateObject();
        cJSON_AddStringToObject(complete_root, "status", "complete");
        cJSON_AddStringToObject(complete_root, "request_id", task->request_id);
        char *complete_json = cJSON_Print(complete_root);
        cJSON_Delete(complete_root);
        
        if (complete_json) {
            socket_send_json(g_agent_ctx, MSG_TYPE_UPDATE_PROGRESS, complete_json);
            free(complete_json);
        }

        /* 延迟2秒后自动重启 */
        sleep(2);
        update_restart_agent();
    }

    free(task);

    /* 清除线程运行标志 */
    pthread_mutex_lock(&g_update_lock);
    g_update_thread_running = false;
    pthread_mutex_unlock(&g_update_lock);

    return NULL;
}

/* 校验下载文件 */
int update_verify_package(const char *filepath)
{
    LOG_INFO("校验文件: %s", filepath);
    
    pthread_mutex_lock(&g_update_lock);
    g_update_status = UPDATE_STATUS_VERIFYING;
    pthread_mutex_unlock(&g_update_lock);
    
    /* 检查文件大小 */
    struct stat st;
    if (stat(filepath, &st) != 0) {
        LOG_ERROR("文件不存在: %s", filepath);
        pthread_mutex_lock(&g_update_lock);
        g_update_status = UPDATE_STATUS_FAILED;
        pthread_mutex_unlock(&g_update_lock);
        return -1;
    }
    
    if (g_update_info.file_size > 0 && st.st_size != g_update_info.file_size) {
        LOG_ERROR("文件大小不匹配: 期望 %lld, 实际 %lld",
                 (long long)g_update_info.file_size, (long long)st.st_size);
        pthread_mutex_lock(&g_update_lock);
        g_update_status = UPDATE_STATUS_FAILED;
        pthread_mutex_unlock(&g_update_lock);
        return -1;
    }
    
    /* 校验SHA256 */
    if (strlen(g_update_info.sha256_checksum) > 0) {
        char actual_sha256[SHA256_DIGEST_LENGTH * 2 + 1];
        if (tcp_calc_sha256(filepath, actual_sha256) == 0) {
            if (strcmp(actual_sha256, g_update_info.sha256_checksum) != 0) {
                LOG_ERROR("SHA256校验失败: 期望 %s, 实际 %s", 
                         g_update_info.sha256_checksum, actual_sha256);
                pthread_mutex_lock(&g_update_lock);
                g_update_status = UPDATE_STATUS_FAILED;
                pthread_mutex_unlock(&g_update_lock);
                return -1;
            }
            LOG_INFO("SHA256校验通过: %s", actual_sha256);
        } else {
            LOG_ERROR("SHA256计算失败");
            pthread_mutex_lock(&g_update_lock);
            g_update_status = UPDATE_STATUS_FAILED;
            pthread_mutex_unlock(&g_update_lock);
            return -1;
        }
    }
    
    pthread_mutex_lock(&g_update_lock);
    g_update_status = UPDATE_STATUS_IDLE;
    pthread_mutex_unlock(&g_update_lock);
    
    return 0;
}

/* 备份当前版本 */
int update_backup_current_version(const char *backup_dir, char *backup_path)
{
    char current_binary[512];
    char backup_file[512];
    time_t now = time(NULL);
    struct tm *tm_info = localtime(&now);
    
    /* 获取当前二进制路径 */
    if (readlink("/proc/self/exe", current_binary, sizeof(current_binary)) < 0) {
        LOG_ERROR("无法获取当前二进制路径: %s", strerror(errno));
        return -1;
    }
    
    /* 创建备份目录 */
    if (mkdir_recursive(backup_dir, 0755) != 0) {
        LOG_ERROR("创建备份目录失败: %s", backup_dir);
        return -1;
    }
    
    /* 生成备份文件名：agent-1.0.0-20240213-120000 */
    char timestamp[64];
    strftime(timestamp, sizeof(timestamp), "%Y%m%d-%H%M%S", tm_info);
    snprintf(backup_file, sizeof(backup_file), "%s/agent-%s-%s",
             backup_dir, AGENT_VERSION, timestamp);
    
    LOG_INFO("备份当前版本: %s -> %s", current_binary, backup_file);
    
    /* 复制文件 */
    FILE *src_fp = fopen(current_binary, "rb");
    FILE *dst_fp = fopen(backup_file, "wb");
    
    if (!src_fp || !dst_fp) {
        LOG_ERROR("打开文件失败: %s", strerror(errno));
        if (src_fp) fclose(src_fp);
        if (dst_fp) fclose(dst_fp);
        return -1;
    }
    
    char buf[65536];
    size_t bytes_read;
    while ((bytes_read = fread(buf, 1, sizeof(buf), src_fp)) > 0) {
        fwrite(buf, 1, bytes_read, dst_fp);
    }
    
    fclose(src_fp);
    fclose(dst_fp);
    
    /* 设置执行权限 */
    if (chmod(backup_file, 0755) != 0) {
        LOG_WARN("设置备份文件权限失败: %s", strerror(errno));
    }
    
    if (backup_path) {
        strcpy(backup_path, backup_file);
    }
    
    return 0;
}

/* 解压更新包 */
static int extract_update_package(const char *package_path, const char *output_dir)
{
    LOG_INFO("解压更新包: %s -> %s", package_path, output_dir);

    /* 创建输出目录 */
    if (mkdir_recursive(output_dir, 0755) != 0) {
        LOG_ERROR("创建临时目录失败: %s", output_dir);
        return -1;
    }

    /* 验证包文件存在 */
    struct stat pkg_st;
    if (stat(package_path, &pkg_st) != 0) {
        LOG_ERROR("包文件不存在: %s", package_path);
        return -1;
    }
    LOG_INFO("包文件大小: %lld 字节", (long long)pkg_st.st_size);

    /* 使用 tar 命令解压（使用绝对路径） */
    /* 注意：使用 --warning=no-timestamp 避免 tar 对时间戳的警告 */
    char extract_cmd[1024];
    snprintf(extract_cmd, sizeof(extract_cmd),
             "tar --warning=no-timestamp -xf '%s' -C '%s' 2>&1",
             package_path, output_dir);

    LOG_INFO("执行解压命令: %s", extract_cmd);
    int rc = system(extract_cmd);

    /* tar 返回值可能为负数，需要检查文件是否正确解压 */
    if (rc != 0) {
        LOG_WARN("tar命令返回非零: %d (可能是警告，继续验证)", rc);
    }

    /* 验证是否成功解压了文件 */
    char new_binary[512];
    snprintf(new_binary, sizeof(new_binary), "%s/buildroot-agent", output_dir);

    struct stat st;
    if (stat(new_binary, &st) != 0) {
        /* tar 失败了，尝试其他方法 */
        LOG_ERROR("未找到解压后的二进制文件: %s", new_binary);
        LOG_ERROR("tar解压失败，请检查tar包是否完整");

        /* 列出目录内容用于调试 */
        char list_cmd[1024];
        snprintf(list_cmd, sizeof(list_cmd), "ls -la '%s'", output_dir);
        LOG_INFO("临时目录内容: %s", list_cmd);
        system(list_cmd);

        /* 尝试列出tar包内容 */
        snprintf(list_cmd, sizeof(list_cmd), "tar -tf '%s'", package_path);
        LOG_INFO("tar包内容: %s", list_cmd);
        system(list_cmd);

        return -1;
    }

    /* 验证文件大小是否合理 */
    if (st.st_size < 1024) {
        LOG_ERROR("解压后的二进制文件太小: %lld 字节 (可能损坏)", (long long)st.st_size);
        return -1;
    }

    LOG_INFO("验证成功: 找到二进制文件 %s (大小: %lld 字节)",
             new_binary, (long long)st.st_size);

    return 0;
}

/* 获取当前二进制路径 */
static char *get_current_binary_path(void)
{
    char *path = (char *)malloc(512);
    if (!path) {
        return NULL;
    }

    ssize_t len = readlink("/proc/self/exe", path, 511);
    if (len < 0) {
        LOG_ERROR("无法获取当前二进制路径: %s", strerror(errno));
        free(path);
        return NULL;
    }
    path[len] = '\0';  /* 确保以 NULL 结尾 */

    return path;
}

/* 安装新二进制 */
static int install_new_binary(const char *new_binary_path)
{
    char *current_binary = get_current_binary_path();
    if (!current_binary) {
        LOG_ERROR("无法获取当前二进制路径");
        return -1;
    }
    
    char *temp_binary = (char *)malloc(strlen(current_binary) + 16);
    if (!temp_binary) {
        free(current_binary);
        return -1;
    }

    char *backup_binary = (char *)malloc(strlen(current_binary) + 16);
    if (!backup_binary) {
        free(current_binary);
        free(temp_binary);
        return -1;
    }

    /* 创建临时文件路径 */
    snprintf(temp_binary, strlen(current_binary) + 16, "%s.new", current_binary);
    snprintf(backup_binary, strlen(current_binary) + 16, "%s.backup", current_binary);
    
    LOG_INFO("安装新版本: %s -> %s", new_binary_path, current_binary);
    
    /* 复制新二进制到临时位置 */
    FILE *src_fp = fopen(new_binary_path, "rb");
    FILE *dst_fp = fopen(temp_binary, "wb");
    
    if (!src_fp || !dst_fp) {
        LOG_ERROR("打开文件失败: %s", strerror(errno));
        free(current_binary);
        free(temp_binary);
        free(backup_binary);
        if (src_fp) fclose(src_fp);
        if (dst_fp) fclose(dst_fp);
        return -1;
    }
    
    char buf[65536];
    size_t bytes_read;
    while ((bytes_read = fread(buf, 1, sizeof(buf), src_fp)) > 0) {
        fwrite(buf, 1, bytes_read, dst_fp);
    }
    
    fclose(src_fp);
    fclose(dst_fp);
    
    /* 设置执行权限 */
    if (chmod(temp_binary, 0755) != 0) {
        LOG_ERROR("设置执行权限失败: %s", strerror(errno));
        unlink(temp_binary);
        free(current_binary);
        free(temp_binary);
        free(backup_binary);
        return -1;
    }
    
    /* 原子替换：当前 -> 备份 */
    if (rename(current_binary, backup_binary) != 0) {
        LOG_ERROR("备份当前版本失败: %s", strerror(errno));
        unlink(temp_binary);
        free(current_binary);
        free(temp_binary);
        free(backup_binary);
        return -1;
    }
    
    /* 原子替换：临时 -> 当前 */
    if (rename(temp_binary, current_binary) != 0) {
        LOG_ERROR("安装新版本失败: %s", strerror(errno));
        /* 尝试恢复备份 */
        rename(backup_binary, current_binary);
        free(current_binary);
        free(temp_binary);
        free(backup_binary);
        return -1;
    }
    
    LOG_INFO("安装成功，备份位置: %s", backup_binary);

    /* 保存备份路径供回退使用 */
    char backup_path_file[512];
    snprintf(backup_path_file, sizeof(backup_path_file),
             "%s/backup/.last_backup", DEFAULT_DATA_DIR);

    mkdir_recursive(DEFAULT_UPDATE_BACKUP_PATH, 0755);

    FILE *bp_fp = fopen(backup_path_file, "w");
    if (bp_fp) {
        fprintf(bp_fp, "%s\n", backup_binary);
        fclose(bp_fp);
        LOG_DEBUG("备份路径已保存到: %s", backup_path_file);
    } else {
        LOG_WARN("无法保存备份路径: %s", backup_path_file);
    }

    free(current_binary);
    free(temp_binary);
    free(backup_binary);

    return 0;
}

/* 验证安装 */
static int verify_installation(void)
{
    /* 验证新版本可以执行 */
    char *binary_path = get_current_binary_path();
    if (!binary_path) {
        return -1;
    }
    
    /* 检查文件是否存在 */
    struct stat st;
    if (stat(binary_path, &st) != 0) {
        free(binary_path);
        return -1;
    }
    
    /* 检查执行权限 */
    if (access(binary_path, X_OK) != 0) {
        LOG_WARN("二进制文件没有执行权限");
        free(binary_path);
        return -1;
    }
    
    free(binary_path);
    return 0;
}

/* 安装更新包 */
int update_install_package(const char *package_path)
{
    LOG_INFO("开始安装更新包: %s", package_path);
    
    pthread_mutex_lock(&g_update_lock);
    g_update_status = UPDATE_STATUS_INSTALLING;
    pthread_mutex_unlock(&g_update_lock);
    
    char temp_dir[512];
    snprintf(temp_dir, sizeof(temp_dir), "%s/update-%lld",
             DEFAULT_UPDATE_TEMP_PATH, (long long)time(NULL));
    
    /* 创建临时目录 */
    mkdir_recursive(DEFAULT_UPDATE_TEMP_PATH, 0755);
    
    /* 解压更新包 */
    LOG_INFO("解压更新包到: %s", temp_dir);
    if (extract_update_package(package_path, temp_dir) != 0) {
        LOG_ERROR("解压失败");
        pthread_mutex_lock(&g_update_lock);
        g_update_status = UPDATE_STATUS_FAILED;
        pthread_mutex_unlock(&g_update_lock);
        return -1;
    }
    
    /* 查找新的二进制文件 */
    char new_binary[512];
    snprintf(new_binary, sizeof(new_binary), "%s/buildroot-agent", temp_dir);
    
    /* 验证新二进制存在 */
    struct stat st;
    if (stat(new_binary, &st) != 0) {
        LOG_ERROR("新二进制文件不存在: %s", new_binary);
        pthread_mutex_lock(&g_update_lock);
        g_update_status = UPDATE_STATUS_FAILED;
        pthread_mutex_unlock(&g_update_lock);
        return -1;
    }
    
    LOG_INFO("新二进制大小: %lld bytes", (long long)st.st_size);
    
    /* 安装新二进制 */
    if (install_new_binary(new_binary) != 0) {
        LOG_ERROR("安装新版本失败");
        pthread_mutex_lock(&g_update_lock);
        g_update_status = UPDATE_STATUS_FAILED;
        pthread_mutex_unlock(&g_update_lock);
        return -1;
    }
    
    /* 验证安装 */
    if (verify_installation() != 0) {
        LOG_ERROR("安装验证失败");
        pthread_mutex_lock(&g_update_lock);
        g_update_status = UPDATE_STATUS_FAILED;
        pthread_mutex_unlock(&g_update_lock);
        return -1;
    }
    
    pthread_mutex_lock(&g_update_lock);
    g_update_status = UPDATE_STATUS_COMPLETE;
    pthread_mutex_unlock(&g_update_lock);
    
    return 0;
}

/* 重启agent */
void update_restart_agent(void)
{
    LOG_INFO("准备重启 Agent...");
    
    /* 删除PID文件，避免子进程启动时冲突 */
    char pid_file[512];
    snprintf(pid_file, sizeof(pid_file), "%s/buildroot-agent.pid", DEFAULT_DATA_DIR);
    remove_pid_file(pid_file);
    
    /* 停止服务 */
    agent_stop();
    
    /* 清理资源 */
    socket_cleanup();
    
    /* 获取配置文件路径 */
    char config_file[512] = DEFAULT_CONFIG_PATH;
    
    /* 获取二进制路径 */
    char *binary_path = get_current_binary_path();
    if (!binary_path) {
        LOG_ERROR("无法获取二进制路径");
        return;
    }
    
    /* 处理.backup后缀（如果读到备份路径，移除后缀）*/
    char *backup_suffix = strstr(binary_path, ".backup");
    if (backup_suffix) {
        LOG_WARN("检测到.backup后缀，移除后缀: %s", binary_path);
        *backup_suffix = '\0';
    }
    
    /* 计算备份路径 */
    char *backup_path = (char *)malloc(strlen(binary_path) + 16);
    if (!backup_path) {
        LOG_ERROR("分配备份路径内存失败");
        free(binary_path);
        return;
    }
    snprintf(backup_path, strlen(binary_path) + 16, "%s.backup", binary_path);
    
    /* 保存备份路径到文件（供回退使用）*/
    char backup_path_file[512];
    snprintf(backup_path_file, sizeof(backup_path_file),
             "%s/backup/.last_backup", DEFAULT_DATA_DIR);
    
    mkdir_recursive(DEFAULT_UPDATE_BACKUP_PATH, 0755);
    
    FILE *bp_fp = fopen(backup_path_file, "w");
    if (bp_fp) {
        fprintf(bp_fp, "%s\n", backup_path);
        fclose(bp_fp);
        LOG_INFO("备份路径已保存: %s", backup_path);
    } else {
        LOG_WARN("无法保存备份路径: %s (%s)", backup_path_file, strerror(errno));
    }
    
    /* 预检查：验证备份文件是否存在（用于回退）*/
    struct stat backup_stat;
    if (stat(backup_path, &backup_stat) == 0) {
        LOG_INFO("备份文件存在: %s (大小: %lld bytes)", backup_path, (long long)backup_stat.st_size);
    } else {
        LOG_WARN("备份文件不存在: %s (回退不可用)", backup_path);
    }
    
    /* 预检查：验证二进制文件 */
    struct stat binary_stat;
    if (stat(binary_path, &binary_stat) != 0) {
        LOG_ERROR("二进制文件不存在: %s (%s)", binary_path, strerror(errno));
        free(binary_path);
        free(backup_path);
        return;
    }
    
    if (!S_ISREG(binary_stat.st_mode)) {
        LOG_ERROR("二进制文件不是常规文件: %s", binary_path);
        free(binary_path);
        free(backup_path);
        return;
    }
    
    if (access(binary_path, X_OK) != 0) {
        LOG_ERROR("二进制文件没有执行权限: %s", binary_path);
        free(binary_path);
        free(backup_path);
        return;
    }
    
    LOG_INFO("二进制文件检查通过: %s (大小: %lld bytes, 权限: 0%o, 备份: %s)",
             binary_path, (long long)binary_stat.st_size, binary_stat.st_mode & 0777, backup_path);
    
    /* 预检查：验证配置文件（警告但不阻止启动）*/
    struct stat config_stat;
    if (stat(config_file, &config_stat) != 0) {
        LOG_WARN("配置文件不存在: %s (将使用默认配置)", config_file);
    } else {
        LOG_INFO("配置文件存在: %s", config_file);
    }
    
    /* 启动新进程 */
    pid_t pid = fork();
    if (pid < 0) {
        LOG_ERROR("fork失败: %s", strerror(errno));
        free(binary_path);
        return;
    }
    
    if (pid == 0) {
        /* 子进程：启动新版本 */
        
        /* 打开错误日志文件（在重定向前）*/
        char error_log_path[512];
        snprintf(error_log_path, sizeof(error_log_path), "%s/temp/agent_restart_error.log",
                 DEFAULT_DATA_DIR);
        int error_log_fd = open(error_log_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        
        setsid();
        
        /* 重定向标准错误到日志文件 */
        if (error_log_fd >= 0) {
            dup2(error_log_fd, STDERR_FILENO);
            close(error_log_fd);
            
            /* 写入启动信息 */
            const char *restart_msg = "=== Agent Restart Log ===\n";
            write(STDERR_FILENO, restart_msg, strlen(restart_msg));
            
            char start_info[512];
            time_t now = time(NULL);
            struct tm *tm_info = localtime(&now);
            char time_str[64];
            strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", tm_info);
            snprintf(start_info, sizeof(start_info),
                     "Time: %s\nBinary: %s\nConfig: %s\n",
                     time_str, binary_path, config_file);
            write(STDERR_FILENO, start_info, strlen(start_info));
        }
        
        /* 重定向标准输入和输出到 /dev/null */
        int null_fd = open("/dev/null", O_RDWR);
        dup2(null_fd, STDIN_FILENO);
        dup2(null_fd, STDOUT_FILENO);
        close(null_fd);
        
        /* 启动agent */
        execl(binary_path, binary_path, "-c", config_file, "--force", NULL);
        
        /* 如果执行到这里，说明exec失败，尝试回退 */
        char err_msg[1024];
        snprintf(err_msg, sizeof(err_msg),
                 "EXEC FAILED!\nError: %s (errno=%d)\nBinary: %s\nConfig: %s\nTrying to rollback to: %s\n",
                 strerror(errno), errno, binary_path, config_file, backup_path);
        write(STDERR_FILENO, err_msg, strlen(err_msg));
        
        /* 尝试回退 */
        if (access(backup_path, F_OK | X_OK) == 0) {
            LOG_INFO("尝试回退到备份: %s", backup_path);
            
            /* 复制备份文件 */
            int src_fd = open(backup_path, O_RDONLY);
            if (src_fd >= 0) {
                off_t size = lseek(src_fd, 0, SEEK_END);
                lseek(src_fd, 0, SEEK_SET);
                
                int dst_fd = open(binary_path, O_WRONLY | O_CREAT | O_TRUNC, 0755);
                if (dst_fd >= 0) {
                    char *buf = malloc(65536);
                    if (buf) {
                        ssize_t bytes;
                        while ((bytes = read(src_fd, buf, 65536)) > 0) {
                            write(dst_fd, buf, bytes);
                        }
                        free(buf);
                    }
                    close(dst_fd);
                    
                    char rollback_msg[256];
                    snprintf(rollback_msg, sizeof(rollback_msg),
                             "Rollback successful: %s -> %s\n", backup_path, binary_path);
                    write(STDERR_FILENO, rollback_msg, strlen(rollback_msg));
                    
                    /* 尝试启动备份版本 */
                    execl(binary_path, binary_path, "-c", config_file, "--force", NULL);
                }
                close(src_fd);
            }
        }
        _exit(1);
    }
    
    /* 释放二进制路径内存 */
    free(binary_path);
    free(backup_path);
    
    /* 父进程：等待并退出 */
    LOG_INFO("新进程已启动 (PID: %d)", pid);
    
    /* 等待2秒确保子进程启动 */
    sleep(2);
    
    if (kill(pid, 0) == 0) {
        LOG_INFO("Agent重启成功");
    } else {
        LOG_ERROR("新进程启动失败，请检查 /tmp/agent_restart_error.log");
    }
    
    /* 父进程退出 */
    _exit(0);
}

/* 回滚到旧版本 */
int update_rollback_to_backup(const char *backup_path)
{
    LOG_INFO("开始回滚到备份: %s", backup_path);
    
    pthread_mutex_lock(&g_update_lock);
    g_update_status = UPDATE_STATUS_ROLLING_BACK;
    pthread_mutex_unlock(&g_update_lock);
    
    if (!backup_path || strlen(backup_path) == 0) {
        /* 尝试从保存的备份路径恢复 */
        char last_backup_path[512];
        snprintf(last_backup_path, sizeof(last_backup_path),
                 "%s/backup/.last_backup", DEFAULT_DATA_DIR);
        
        FILE *fp = fopen(last_backup_path, "r");
        if (fp) {
            char backup_path_buf[512];
            if (fgets(backup_path_buf, sizeof(backup_path_buf), fp)) {
                /* 去除换行符 */
                char *newline = strchr(backup_path_buf, '\n');
                if (newline) *newline = '\0';
                backup_path = backup_path_buf;
            }
            fclose(fp);
        }
    }
    
    char *current_binary = get_current_binary_path();
    if (!current_binary) {
        LOG_ERROR("无法获取当前二进制路径");
        pthread_mutex_lock(&g_update_lock);
        g_update_status = UPDATE_STATUS_FAILED;
        pthread_mutex_unlock(&g_update_lock);
        return -1;
    }
    
    /* 验证备份文件存在 */
    struct stat st;
    if (stat(backup_path, &st) != 0) {
        LOG_ERROR("备份文件不存在: %s", backup_path);
        pthread_mutex_lock(&g_update_lock);
        g_update_status = UPDATE_STATUS_FAILED;
        pthread_mutex_unlock(&g_update_lock);
        free(current_binary);
        return -1;
    }
    
    /* 停止当前进程 */
    agent_stop();
    socket_cleanup();
    
    /* 复制备份到当前位置 */
    if (copy_file(backup_path, current_binary) != 0) {
        LOG_ERROR("回滚失败: 无法复制备份文件");
        pthread_mutex_lock(&g_update_lock);
        g_update_status = UPDATE_STATUS_FAILED;
        pthread_mutex_unlock(&g_update_lock);
        free(current_binary);
        return -1;
    }
    
    /* 设置执行权限 */
    if (chmod(current_binary, 0755) != 0) {
        LOG_ERROR("设置执行权限失败: %s", strerror(errno));
        pthread_mutex_lock(&g_update_lock);
        g_update_status = UPDATE_STATUS_FAILED;
        pthread_mutex_unlock(&g_update_lock);
        free(current_binary);
        return -1;
    }
    
    pthread_mutex_lock(&g_update_lock);
    g_update_status = UPDATE_STATUS_ROLLBACK_COMPLETE;
    pthread_mutex_unlock(&g_update_lock);
    
    LOG_INFO("回滚成功");
    free(current_binary);
    
    /* 启动回滚后的进程 */
    pid_t pid = fork();
    if (pid < 0) {
        LOG_ERROR("fork失败: %s", strerror(errno));
        free(current_binary);
        return -1;
    }
    
    if (pid == 0) {
        setsid();
        execl(current_binary, current_binary, NULL);
        exit(1);
    }
    
    free(current_binary);
    _exit(0);
}

/* 报告更新状态 */
int update_report_status(agent_context_t *ctx, update_status_t status, const char *message, int progress)
{
    if (!ctx) return -1;
    
    pthread_mutex_lock(&g_update_lock);
    g_update_status = status;
    pthread_mutex_unlock(&g_update_lock);
    
    LOG_INFO("更新状态: %d, 进度: %d%%, 消息: %s",
             status, progress, message ? message : "");
    
    /* 发送进度到服务器 */
    if (progress >= 0) {
        send_update_progress(ctx, progress, message);
    }
    
    return 0;
}

/* 发送更新可用通知给服务器 */
int update_notify_available(agent_context_t *ctx)
{
    if (!ctx) return -1;
    
    pthread_mutex_lock(&g_update_lock);
    
    if (!g_update_info.has_update) {
        pthread_mutex_unlock(&g_update_lock);
        return 0;
    }
    
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "current_version", AGENT_VERSION);
    cJSON_AddStringToObject(root, "latest_version", g_update_info.latest_version);
    cJSON_AddStringToObject(root, "release_notes", g_update_info.release_notes);
    cJSON_AddNumberToObject(root, "file_size", (double)g_update_info.file_size);
    cJSON_AddStringToObject(root, "sha256_checksum", g_update_info.sha256_checksum);
    cJSON_AddBoolToObject(root, "mandatory", g_update_info.mandatory);
    
    char request_id[128];
    snprintf(request_id, sizeof(request_id), "available-%lld", (long long)get_timestamp_ms());
    cJSON_AddStringToObject(root, "request_id", request_id);
    
    pthread_mutex_unlock(&g_update_lock);
    
    char *json = cJSON_Print(root);
    cJSON_Delete(root);
    
    if (!json) {
        LOG_ERROR("JSON生成失败");
        return -1;
    }
    
    int rc = socket_send_json(ctx, MSG_TYPE_UPDATE_AVAILABLE, json);
    free(json);
    
    if (rc == 0) {
        LOG_INFO("已发送更新可用通知: %s -> %s",
                 AGENT_VERSION, g_update_info.latest_version);
    }
    
    return rc;
}
