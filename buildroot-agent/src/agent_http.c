/*
 * agent_http.c - HTTP通信模块（基于libcurl）
 */

#include "agent.h"
#include <curl/curl.h>
#include <openssl/md5.h>
#include <openssl/sha.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>

/* 全局变量 */
static CURL *g_curl_handle = NULL;
static bool g_curl_initialized = false;

/* 写入数据回调 */
static size_t write_data_callback(void *ptr, size_t size, size_t nmemb, void *stream)
{
    size_t written = fwrite(ptr, size, nmemb, (FILE *)stream);
    return written;
}

/* 进度回调 */
static int progress_callback(void *clientp,
    curl_off_t dltotal,
    curl_off_t dlnow,
    curl_off_t ultotal,
    curl_off_t ulnow)
{
    http_download_config_t *config = (http_download_config_t *)clientp;
    if (config && config->callback) {
        int progress = 0;
        if (dltotal > 0) {
            progress = (int)((dlnow * 100) / dltotal);
        }
        config->callback(config->url, progress, dlnow, dltotal, config->user_data);
    }
    return 0;
}

/* 初始化libcurl */
int http_init(void)
{
    if (g_curl_initialized) {
        return 0;  /* 已初始化 */
    }
    
    CURLcode rc = curl_global_init(CURL_GLOBAL_DEFAULT);
    if (rc != CURLE_OK) {
        LOG_ERROR("初始化libcurl失败: %s", curl_easy_strerror(rc));
        return -1;
    }
    
    g_curl_handle = curl_easy_init();
    if (!g_curl_handle) {
        LOG_ERROR("创建CURL句柄失败");
        curl_global_cleanup();
        return -1;
    }
    
    g_curl_initialized = true;
    LOG_INFO("libcurl初始化成功 (版本: %s)", curl_version());
    
    return 0;
}

/* 清理libcurl */
void http_cleanup(void)
{
    if (g_curl_handle) {
        curl_easy_cleanup(g_curl_handle);
        g_curl_handle = NULL;
    }
    
    if (g_curl_initialized) {
        curl_global_cleanup();
        g_curl_initialized = false;
    }
    
    LOG_DEBUG("libcurl已清理");
}

/* HTTP GET 请求（获取字符串）*/
char *http_get_string(const char *url, int timeout)
{
    if (!g_curl_initialized) {
        LOG_ERROR("libcurl未初始化");
        return NULL;
    }
    
    if (!url) {
        LOG_ERROR("URL为空");
        return NULL;
    }
    
    LOG_DEBUG("HTTP GET: %s", url);
    
    /* 使用内存缓冲区接收数据 */
    char *response_buf = NULL;
    size_t response_size = 0;
    size_t response_capacity = 0;
    
    curl_easy_setopt(g_curl_handle, CURLOPT_URL, url);
    curl_easy_setopt(g_curl_handle, CURLOPT_WRITEFUNCTION, write_data_callback);
    curl_easy_setopt(g_curl_handle, CURLOPT_WRITEDATA, &response_buf);
    curl_easy_setopt(g_curl_handle, CURLOPT_WRITEDATA, &response_size);
    
    /* 自定义写入处理，使用内存 */
    curl_easy_setopt(g_curl_handle, CURLOPT_NOPROGRESS, 1L);
    curl_easy_setopt(g_curl_handle, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(g_curl_handle, CURLOPT_MAXREDIRS, 5L);
    
    if (timeout > 0) {
        curl_easy_setopt(g_curl_handle, CURLOPT_TIMEOUT, timeout);
        curl_easy_setopt(g_curl_handle, CURLOPT_CONNECTTIMEOUT, 10);
    }
    
    /* 执行请求 */
    CURLcode rc = curl_easy_perform(g_curl_handle);
    
    /* 释放缓冲区 */
    if (response_buf) {
        free(response_buf);
    }
    
    if (rc != CURLE_OK) {
        LOG_ERROR("HTTP GET失败: %s", curl_easy_strerror(rc));
        return NULL;
    }
    
    long http_code = 0;
    curl_easy_getinfo(g_curl_handle, CURLINFO_RESPONSE_CODE, &http_code);
    
    if (http_code != 200) {
        LOG_ERROR("HTTP错误: %ld", http_code);
        return NULL;
    }
    
    /* 读取响应 */
    char *response = NULL;
    curl_off_t content_length = 0;
    curl_easy_getinfo(g_curl_handle, CURLINFO_CONTENT_LENGTH_DOWNLOAD, &content_length);
    
    if (content_length > 0 && content_length < 1024 * 1024) {  /* 限制1MB */
        response = (char *)malloc(content_length + 1);
        if (response) {
            curl_easy_setopt(g_curl_handle, CURLOPT_WRITEFUNCTION, fwrite);
            curl_easy_setopt(g_curl_handle, CURLOPT_WRITEDATA, response);
            curl_easy_setopt(g_curl_handle, CURLOPT_POSTFIELDSIZE, content_length);
            
            rc = curl_easy_perform(g_curl_handle);
            if (rc == CURLE_OK) {
                response[content_length] = '\0';
            } else {
                free(response);
                response = NULL;
            }
        }
    }
    
    LOG_DEBUG("HTTP GET成功: %s", response ? "有响应体" : "无响应体");
    return response;
}

/* HTTP POST 请求（发送JSON）*/
char *http_post_json(const char *url, const char *json, int timeout)
{
    if (!g_curl_initialized) {
        LOG_ERROR("libcurl未初始化");
        return NULL;
    }
    
    if (!url || !json) {
        LOG_ERROR("URL或JSON为空");
        return NULL;
    }
    
    LOG_DEBUG("HTTP POST: %s", url);
    
    /* 设置请求头 */
    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    curl_easy_setopt(g_curl_handle, CURLOPT_HTTPHEADER, headers);
    
    /* 设置POST数据 */
    curl_easy_setopt(g_curl_handle, CURLOPT_URL, url);
    curl_easy_setopt(g_curl_handle, CURLOPT_POSTFIELDS, json);
    curl_easy_setopt(g_curl_handle, CURLOPT_POSTFIELDSIZE, strlen(json));
    
    /* 接收响应 */
    char *response = NULL;
    curl_easy_setopt(g_curl_handle, CURLOPT_WRITEDATA, &response);
    
    curl_easy_setopt(g_curl_handle, CURLOPT_NOPROGRESS, 1L);
    curl_easy_setopt(g_curl_handle, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(g_curl_handle, CURLOPT_MAXREDIRS, 5L);
    
    if (timeout > 0) {
        curl_easy_setopt(g_curl_handle, CURLOPT_TIMEOUT, timeout);
        curl_easy_setopt(g_curl_handle, CURLOPT_CONNECTTIMEOUT, 10);
    }
    
    /* 执行请求 */
    CURLcode rc = curl_easy_perform(g_curl_handle);
    curl_slist_free_all(headers);
    
    if (rc != CURLE_OK) {
        LOG_ERROR("HTTP POST失败: %s", curl_easy_strerror(rc));
        return NULL;
    }
    
    long http_code = 0;
    curl_easy_getinfo(g_curl_handle, CURLINFO_RESPONSE_CODE, &http_code);
    
    if (http_code != 200) {
        LOG_ERROR("HTTP错误: %ld", http_code);
        return NULL;
    }
    
    LOG_DEBUG("HTTP POST成功: %s", response ? "有响应体" : "无响应体");
    return response;
}

/* 下载文件 */
int http_download_file(
    const char *url,
    const char *output_path,
    http_download_config_t *config)
{
    if (!g_curl_initialized) {
        LOG_ERROR("libcurl未初始化");
        return -1;
    }
    
    if (!url || !output_path) {
        LOG_ERROR("URL或输出路径为空");
        return -1;
    }
    
    LOG_INFO("开始下载: %s -> %s", url, output_path);
    
    FILE *fp = NULL;
    CURLcode rc;
    http_download_config_t default_config;
    
    /* 使用默认配置 */
    if (config) {
        memcpy(&default_config, config, sizeof(http_download_config_t));
    } else {
        memset(&default_config, 0, sizeof(http_download_config_t));
        strncpy(default_config.url, url, sizeof(default_config.url) - 1);
        strncpy(default_config.output_path, output_path, sizeof(default_config.output_path) - 1);
        default_config.timeout = DEFAULT_DOWNLOAD_TIMEOUT;
        default_config.max_speed = DEFAULT_MAX_DOWNLOAD_SPEED;
        default_config.enable_resume = true;
        default_config.verify_ssl = true;
        default_config.callback = NULL;
        default_config.user_data = NULL;
    }
    
    /* 打开输出文件 */
    if (default_config.enable_resume) {
        /* 断点续传：追加模式 */
        fp = fopen(default_config.output_path, "ab");
        if (fp) {
            /* 获取已下载大小 */
            fseek(fp, 0, SEEK_END);
            curl_off_t downloaded = ftello(fp);
            
            /* 设置断点续传 */
            curl_easy_setopt(g_curl_handle, CURLOPT_RESUME_FROM_LARGE, downloaded);
            LOG_INFO("断点续传: 从位置 %llu", (unsigned long long)downloaded);
        }
    } else {
        /* 正常下载：新建文件 */
        fp = fopen(default_config.output_path, "wb");
    }
    
    if (!fp) {
        LOG_ERROR("无法打开文件: %s", default_config.output_path);
        return -1;
    }
    
    /* 配置CURL选项 */
    curl_easy_setopt(g_curl_handle, CURLOPT_URL, default_config.url);
    curl_easy_setopt(g_curl_handle, CURLOPT_WRITEFUNCTION, write_data_callback);
    curl_easy_setopt(g_curl_handle, CURLOPT_WRITEDATA, fp);
    curl_easy_setopt(g_curl_handle, CURLOPT_NOPROGRESS, default_config.callback ? 0L : 1L);
    curl_easy_setopt(g_curl_handle, CURLOPT_PROGRESSFUNCTION, progress_callback);
    curl_easy_setopt(g_curl_handle, CURLOPT_PROGRESSDATA, &default_config);
    
    /* SSL配置 */
    if (!default_config.verify_ssl) {
        curl_easy_setopt(g_curl_handle, CURLOPT_SSL_VERIFYPEER, 0L);
        curl_easy_setopt(g_curl_handle, CURLOPT_SSL_VERIFYHOST, 0L);
        LOG_WARN("SSL证书验证已禁用");
    } else {
        /* 设置CA证书路径 */
        if (default_config.ca_cert_path[0] != '\0') {
            curl_easy_setopt(g_curl_handle, CURLOPT_CAINFO, default_config.ca_cert_path);
        }
    }
    
    /* 速度限制 */
    if (default_config.max_speed > 0) {
        curl_easy_setopt(g_curl_handle, CURLOPT_MAX_RECV_SPEED_LARGE, 
                          (curl_off_t)default_config.max_speed);
    }
    
    /* 超时设置 */
    if (default_config.timeout > 0) {
        curl_easy_setopt(g_curl_handle, CURLOPT_TIMEOUT, default_config.timeout);
        curl_easy_setopt(g_curl_handle, CURLOPT_CONNECTTIMEOUT, 30);
    }
    
    /* 启用重试 */
    curl_easy_setopt(g_curl_handle, CURLOPT_MAXREDIRS, 5L);
    curl_easy_setopt(g_curl_handle, CURLOPT_FOLLOWLOCATION, 1L);
    
    /* 执行下载 */
    rc = curl_easy_perform(g_curl_handle);
    
    fclose(fp);
    
    if (rc != CURLE_OK) {
        LOG_ERROR("下载失败: %s", curl_easy_strerror(rc));
        return -1;
    }
    
    long http_code = 0;
    curl_easy_getinfo(g_curl_handle, CURLINFO_RESPONSE_CODE, &http_code);
    
    if (http_code != 200 && http_code != 206) {
        LOG_ERROR("HTTP错误: %ld", http_code);
        return -1;
    }
    
    LOG_INFO("下载完成: %s", default_config.output_path);
    return 0;
}

/* 检查断点续传支持 */
int http_can_resume(const char *url, const char *output_path)
{
    struct stat st;
    if (stat(output_path, &st) != 0) {
        /* 文件不存在，不支持续传 */
        return 0;
    }
    
    /* 文件存在，可以尝试续传 */
    return 1;
}

/* 计算文件MD5 */
int http_calc_md5(const char *filepath, char *md5_str)
{
    if (!filepath || !md5_str) {
        return -1;
    }
    
    FILE *fp = fopen(filepath, "rb");
    if (!fp) {
        LOG_ERROR("无法打开文件: %s", filepath);
        return -1;
    }
    
    MD5_CTX md5_ctx;
    MD5_Init(&md5_ctx);
    
    unsigned char buf[8192];
    size_t bytes_read;
    while ((bytes_read = fread(buf, 1, sizeof(buf), fp)) > 0) {
        MD5_Update(&md5_ctx, buf, bytes_read);
    }
    
    fclose(fp);
    
    unsigned char md5_digest[MD5_DIGEST_LENGTH];
    MD5_Final(md5_digest, &md5_ctx);
    
    /* 转换为十六进制字符串 */
    for (int i = 0; i < MD5_DIGEST_LENGTH; i++) {
        sprintf(md5_str + i * 2, "%02x", md5_digest[i]);
    }
    md5_str[MD5_DIGEST_LENGTH * 2] = '\0';
    
    return 0;
}

/* 计算文件SHA256 */
int http_calc_sha256(const char *filepath, char *sha256_str)
{
    if (!filepath || !sha256_str) {
        return -1;
    }
    
    FILE *fp = fopen(filepath, "rb");
    if (!fp) {
        LOG_ERROR("无法打开文件: %s", filepath);
        return -1;
    }
    
    SHA256_CTX sha256_ctx;
    SHA256_Init(&sha256_ctx);
    
    unsigned char buf[8192];
    size_t bytes_read;
    while ((bytes_read = fread(buf, 1, sizeof(buf), fp)) > 0) {
        SHA256_Update(&sha256_ctx, buf, bytes_read);
    }
    
    fclose(fp);
    
    unsigned char sha256_digest[SHA256_DIGEST_LENGTH];
    SHA256_Final(sha256_digest, &sha256_ctx);
    
    /* 转换为十六进制字符串 */
    for (int i = 0; i < SHA256_DIGEST_LENGTH; i++) {
        sprintf(sha256_str + i * 2, "%02x", sha256_digest[i]);
    }
    sha256_str[SHA256_DIGEST_LENGTH * 2] = '\0';
    
    return 0;
}

/* 验证校验和 */
bool http_verify_checksum(
    const char *filepath,
    const char *expected_md5,
    const char *expected_sha256)
{
    if (!filepath) {
        return false;
    }
    
    /* 验证MD5 */
    if (expected_md5 && strlen(expected_md5) > 0) {
        char actual_md5[MD5_DIGEST_LENGTH * 2 + 1];
        if (http_calc_md5(filepath, actual_md5) == 0) {
            if (strcmp(actual_md5, expected_md5) != 0) {
                LOG_ERROR("MD5校验失败: 期望 %s, 实际 %s", expected_md5, actual_md5);
                return false;
            }
            LOG_INFO("MD5校验通过: %s", actual_md5);
        } else {
            LOG_ERROR("MD5计算失败");
            return false;
        }
    }
    
    /* 验证SHA256（可选）*/
    if (expected_sha256 && strlen(expected_sha256) > 0) {
        char actual_sha256[SHA256_DIGEST_LENGTH * 2 + 1];
        if (http_calc_sha256(filepath, actual_sha256) == 0) {
            if (strcmp(actual_sha256, expected_sha256) != 0) {
                LOG_ERROR("SHA256校验失败: 期望 %s, 实际 %s", expected_sha256, actual_sha256);
                return false;
            }
            LOG_INFO("SHA256校验通过: %s", actual_sha256);
        } else {
            LOG_ERROR("SHA256计算失败");
            return false;
        }
    }
    
    return true;
}
