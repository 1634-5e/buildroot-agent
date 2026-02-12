/*
 * agent_update.c - 更新管理模块
 */

#include "agent.h"
#include <openssl/md5.h>
#include <openssl/sha.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>

/* 全局变量 */
static update_status_t g_update_status = UPDATE_STATUS_IDLE;
static pthread_mutex_t g_update_lock = PTHREAD_MUTEX_INITIALIZER;
static update_info_t g_update_info;
static pthread_t g_update_thread;
static bool g_update_thread_running = false;

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
    
    char *json = malloc(512);
    if (!json) {
        LOG_ERROR("内存分配失败");
        return -1;
    }
    
    snprintf(json, 512,
             "{\"progress\":%d,\"message\":\"%s\",\"status\":\"downloading\"}",
             progress, message ? message : "");
    
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
    char *json = malloc(512);
    if (!json) {
        LOG_ERROR("内存分配失败");
        return -1;
    }
    
    snprintf(json, 512,
             "{\"device_id\":\"%s\","
             "\"current_version\":\"%s\","
             "\"channel\":\"%s\"}",
             ctx->config.device_id,
             AGENT_VERSION,
             ctx->config.update_channel);
    
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
    
    /* 配置TCP下载参数 */
    tcp_download_config_t config;
    memset(&config, 0, sizeof(tcp_download_config_t));
    strncpy(config.file_path, url, sizeof(config.file_path) - 1);
    strncpy(config.output_path, output_path, sizeof(config.output_path) - 1);
    config.timeout = DEFAULT_DOWNLOAD_TIMEOUT;
    config.chunk_size = 32768;      /* 32KB块大小 */
    config.max_retries = 3;
    config.callback = callback;
    config.user_data = user_data;
    
    /* 执行TCP下载 */
    return tcp_download_file(g_agent_ctx, url, output_path, &config);
}

/* 校验下载文件 */
int update_verify_package(const char *filepath, const char *expected_md5, const char *expected_sha256)
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
    
    /* 校验MD5 */
    if (expected_md5 && strlen(expected_md5) > 0) {
        char actual_md5[MD5_DIGEST_LENGTH * 2 + 1];
        if (tcp_calc_md5(filepath, actual_md5) == 0) {
            if (strcmp(actual_md5, expected_md5) != 0) {
                LOG_ERROR("MD5校验失败: 期望 %s, 实际 %s", expected_md5, actual_md5);
                pthread_mutex_lock(&g_update_lock);
                g_update_status = UPDATE_STATUS_FAILED;
                pthread_mutex_unlock(&g_update_lock);
                return -1;
            }
            LOG_INFO("MD5校验通过: %s", actual_md5);
        } else {
            LOG_ERROR("MD5计算失败");
            pthread_mutex_lock(&g_update_lock);
            g_update_status = UPDATE_STATUS_FAILED;
            pthread_mutex_unlock(&g_update_lock);
            return -1;
        }
    }
    
    /* 校验SHA256（可选）*/
    if (expected_sha256 && strlen(expected_sha256) > 0) {
        char actual_sha256[SHA256_DIGEST_LENGTH * 2 + 1];
        if (tcp_calc_sha256(filepath, actual_sha256) == 0) {
            if (strcmp(actual_sha256, expected_sha256) != 0) {
                LOG_ERROR("SHA256校验失败: 期望 %s, 实际 %s", expected_sha256, actual_sha256);
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
    LOG_INFO("解压更新包到: %s", output_dir);
    
    /* 创建输出目录 */
    if (mkdir_recursive(output_dir, 0755) != 0) {
        LOG_ERROR("创建临时目录失败: %s", output_dir);
        return -1;
    }
    
    char extract_cmd[1024];
    snprintf(extract_cmd, sizeof(extract_cmd),
             "cd %s && tar -xzf %s 2>&1",
             output_dir, package_path);
    
    int rc = system(extract_cmd);
    if (rc != 0) {
        LOG_ERROR("解压失败: %d", rc);
        return -1;
    }
    
    return 0;
}

/* 获取当前二进制路径 */
static char *get_current_binary_path(void)
{
    char *path = (char *)malloc(512);
    if (!path) {
        return NULL;
    }
    
    if (readlink("/proc/self/exe", path, sizeof(path)) < 0) {
        LOG_ERROR("无法获取当前二进制路径");
        free(path);
        return NULL;
    }
    
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
    
    char *temp_binary = (char *)malloc(strlen(current_binary) + 5);
    if (!temp_binary) {
        free(current_binary);
        return -1;
    }
    
    char *backup_binary = (char *)malloc(strlen(current_binary) + 7);
    if (!backup_binary) {
        free(current_binary);
        free(temp_binary);
        return -1;
    }
    
    /* 创建临时文件路径 */
    sprintf(temp_binary, "%s.new", current_binary);
    sprintf(backup_binary, "%s.backup", current_binary);
    
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
    
    /* 启动新进程 */
    pid_t pid = fork();
    if (pid < 0) {
        LOG_ERROR("fork失败: %s", strerror(errno));
        return;
    }
    
    if (pid == 0) {
        /* 子进程：启动新版本 */
        setsid();
        
        /* 重定向标准输入/输出/错误 */
        int null_fd = open("/dev/null", O_RDWR);
        dup2(null_fd, STDIN_FILENO);
        dup2(null_fd, STDOUT_FILENO);
        dup2(null_fd, STDERR_FILENO);
        close(null_fd);
        
        /* 启动agent */
        execl(binary_path, binary_path, "-c", config_file, NULL);
        
        /* 如果执行到这里，说明exec失败 */
        LOG_ERROR("exec失败: %s", strerror(errno));
        exit(1);
    }
    
    /* 父进程：等待并退出 */
    LOG_INFO("新进程已启动 (PID: %d)", pid);
    
    /* 等待2秒确保子进程启动 */
    sleep(2);
    
    if (kill(pid, 0) == 0) {
        LOG_INFO("Agent重启成功");
    } else {
        LOG_ERROR("新进程启动失败，可能需要手动干预");
    }
    
    /* 父进程退出，让主进程重新启动 */
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
                 "%s/.last_backup", DEFAULT_UPDATE_BACKUP_PATH);
        
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
