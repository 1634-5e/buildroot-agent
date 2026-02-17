/*
 * 工具函数模块
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <ctype.h>
#include <time.h>
#include <sys/time.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <signal.h>
#include "agent.h"

/* 全局日志级别 */
static int g_log_level = LOG_LEVEL_INFO;
static FILE *g_log_file = NULL;

/* 日志级别名称 */
static const char *log_level_names[] = {
    "DEBUG", "INFO", "WARN", "ERROR"
};

/* 设置日志级别 */
void set_log_level(int level)
{
    g_log_level = level;
}

/* 设置日志文件 */
int set_log_file(const char *path)
{
    if (g_log_file && g_log_file != stderr) {
        fclose(g_log_file);
    }
    
    g_log_file = fopen(path, "a");
    if (!g_log_file) {
        g_log_file = stderr;
        return -1;
    }
    
    return 0;
}

/* 日志输出 */
void agent_log(int level, const char *fmt, ...)
{
    if (level < g_log_level) return;
    
    FILE *out = g_log_file ? g_log_file : stderr;
    
    /* 时间戳 */
    struct timeval tv;
    gettimeofday(&tv, NULL);
    struct tm *tm = localtime(&tv.tv_sec);
    
    fprintf(out, "[%04d-%02d-%02d %02d:%02d:%02d.%03ld] [%s] ",
            tm->tm_year + 1900, tm->tm_mon + 1, tm->tm_mday,
            tm->tm_hour, tm->tm_min, tm->tm_sec,
            tv.tv_usec / 1000,
            log_level_names[level]);
    
    va_list args;
    va_start(args, fmt);
    vfprintf(out, fmt, args);
    va_end(args);
    
    fprintf(out, "\n");
    fflush(out);
}

/* 读取文件内容 */
char *read_file_content(const char *path, size_t *size)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        LOG_ERROR("无法打开文件: %s", path);
        return NULL;
    }
    
    fseek(fp, 0, SEEK_END);
    long file_size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    char *content = malloc(file_size + 1);
    if (!content) {
        fclose(fp);
        return NULL;
    }
    
    size_t read_size = fread(content, 1, file_size, fp);
    fclose(fp);
    
    content[read_size] = '\0';
    
    if (size) *size = read_size;
    
    return content;
}

/* 写入文件内容 */
int write_file_content(const char *path, const char *content, size_t size)
{
    FILE *fp = fopen(path, "wb");
    if (!fp) {
        LOG_ERROR("无法创建文件: %s", path);
        return -1;
    }

    size_t written = fwrite(content, 1, size, fp);
    fclose(fp);

    return (written == size) ? 0 : -1;
}

/* Base64解码表 */
static const int base64_decode_table[128] = {
    -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,-1,
    -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,-1,
    -1,-1,-1,-1, -1,-1,-1,-1, -1,-1,-1,62, -1,-1,-1,63,
    52,53,54,55, 56,57,58,59, 60,61,-1,-1, -1,-1,-1,-1,
    -1, 0, 1, 2,  3, 4, 5, 6,  7, 8, 9,10, 11,12,13,14,
    15,16,17,18, 19,20,21,22, 23,24,25,-1, -1,-1,-1,-1,
    -1,26,27,28, 29,30,31,32, 33,34,35,36, 37,38,39,40,
    41,42,43,44, 45,46,47,48, 49,50,51,-1, -1,-1,-1,-1
};

/* Base64解码函数 */
size_t base64_decode(const char *input, unsigned char *output)
{
    size_t input_len = strlen(input);
    size_t output_len = 0;
    int val = 0, valb = -8;

    for (size_t i = 0; i < input_len; i++) {
        char c = input[i];
        if (c == '=') break;
        if ((c < 0) || (c > 127) || (base64_decode_table[(int)c] < 0)) continue;

        val = (val << 6) + base64_decode_table[(int)c];
        valb += 6;
        if (valb >= 0) {
            output[output_len++] = (val >> valb) & 0xFF;
            valb -= 8;
        }
    }

    return output_len;
}

char *get_exe_path(void)
{
    char *path = malloc(512);
    if (!path) return NULL;
    
    ssize_t len = readlink("/proc/self/exe", path, 511);
    if (len < 0) {
        free(path);
        return NULL;
    }
    path[len] = '\0';
    return path;
}

char *get_exe_dir(void)
{
    char *path = get_exe_path();
    if (!path) return NULL;
    
    char *last_slash = strrchr(path, '/');
    if (last_slash) {
        *last_slash = '\0';
    }
    return path;
}

/* 获取设备ID */
char *get_device_id(void)
{
    static char device_id[64] = {0};
    
    if (device_id[0] != '\0') {
        return device_id;
    }
    
    /* 尝试从多个来源获取唯一ID */
    
    /* 1. 尝试读取machine-id */
    FILE *fp = fopen("/etc/machine-id", "r");
    if (fp) {
        if (fgets(device_id, sizeof(device_id), fp)) {
            /* 移除换行符 */
            char *newline = strchr(device_id, '\n');
            if (newline) *newline = '\0';
        }
        fclose(fp);
        if (device_id[0] != '\0') return device_id;
    }
    
    /* 2. 尝试读取product_uuid */
    fp = fopen("/sys/class/dmi/id/product_uuid", "r");
    if (fp) {
        if (fgets(device_id, sizeof(device_id), fp)) {
            char *newline = strchr(device_id, '\n');
            if (newline) *newline = '\0';
        }
        fclose(fp);
        if (device_id[0] != '\0') return device_id;
    }
    
    /* 3. 使用MAC地址生成 */
    fp = fopen("/sys/class/net/eth0/address", "r");
    if (!fp) {
        fp = fopen("/sys/class/net/wlan0/address", "r");
    }
    if (fp) {
        char mac[20] = {0};
        if (fgets(mac, sizeof(mac), fp)) {
            /* 移除冒号和换行 */
            int j = 0;
            for (int i = 0; mac[i] && j < 63; i++) {
                if (mac[i] != ':' && mac[i] != '\n') {
                    device_id[j++] = mac[i];
                }
            }
            device_id[j] = '\0';
        }
        fclose(fp);
        if (device_id[0] != '\0') return device_id;
    }
    
    /* 4. 最后使用随机ID */
    srand(time(NULL));
    snprintf(device_id, sizeof(device_id), "agent-%08x%08x",
             rand(), rand());
    
    return device_id;
}

/* 获取毫秒级时间戳 */
uint64_t get_timestamp_ms(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (uint64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}

/* 创建目录（递归） */
int mkdir_recursive(const char *path, mode_t mode)
{
    char tmp[256];
    strncpy(tmp, path, sizeof(tmp) - 1);
    
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            if (mkdir(tmp, mode) != 0 && errno != EEXIST) {
                return -1;
            }
            *p = '/';
        }
    }
    
    if (mkdir(tmp, mode) != 0 && errno != EEXIST) {
        return -1;
    }
    
    return 0;
}

/* 检查文件是否存在 */
bool file_exists(const char *path)
{
    struct stat st;
    return stat(path, &st) == 0;
}

/* 获取文件大小 */
long get_file_size(const char *path)
{
    struct stat st;
    if (stat(path, &st) != 0) {
        return -1;
    }
    return st.st_size;
}

/* 安全字符串复制 */
void safe_strncpy(char *dest, const char *src, size_t size)
{
    if (size == 0) return;
    strncpy(dest, src, size - 1);
    dest[size - 1] = '\0';
}

/* 去除字符串首尾空格 */
char *str_trim(char *str)
{
    if (!str) return NULL;
    
    /* 去除首部空格 */
    while (*str && isspace(*str)) str++;
    
    if (*str == '\0') return str;
    
    /* 去除尾部空格 */
    char *end = str + strlen(str) - 1;
    while (end > str && isspace(*end)) end--;
    *(end + 1) = '\0';
    
    return str;
}

/* 守护进程化 */
int daemonize(void)
{
    pid_t pid = fork();
    if (pid < 0) {
        return -1;
    }
    if (pid > 0) {
        _exit(0);  /* 父进程退出 */
    }
    
    /* 创建新会话 */
    if (setsid() < 0) {
        return -1;
    }
    
    /* 再次fork，确保不会获取控制终端 */
    pid = fork();
    if (pid < 0) {
        return -1;
    }
    if (pid > 0) {
        _exit(0);
    }
    
    /* 改变工作目录 */
    chdir("/");
    
    /* 重定向标准输入输出 */
    close(STDIN_FILENO);
    close(STDOUT_FILENO);
    close(STDERR_FILENO);
    
    open("/dev/null", O_RDONLY);
    open("/dev/null", O_WRONLY);
    open("/dev/null", O_WRONLY);
    
    return 0;
}

/* 写入PID文件 */
int write_pid_file(const char *path)
{
    FILE *fp = fopen(path, "w");
    if (!fp) {
        return -1;
    }
    fprintf(fp, "%d\n", getpid());
    fclose(fp);
    return 0;
}

/* 删除PID文件 */
void remove_pid_file(const char *path)
{
    unlink(path);
}

/* 检查进程是否运行 */
bool is_process_running(const char *pid_file)
{
    FILE *fp = fopen(pid_file, "r");
    if (!fp) {
        return false;
    }
    
    int pid;
    if (fscanf(fp, "%d", &pid) != 1) {
        fclose(fp);
        return false;
    }
    fclose(fp);
    
    /* 检查进程是否存在 */
    if (kill(pid, 0) == 0) {
        return true;
    }
    
    return false;
}

/* 文件复制函数 */
int copy_file(const char *src_path, const char *dst_path)
{
    FILE *src_fp, *dst_fp;
    char buffer[65536];
    size_t bytes_read;
    
    if (!src_path || !dst_path) {
        return -1;
    }
    
    /* 打开源文件 */
    src_fp = fopen(src_path, "rb");
    if (!src_fp) {
        return -1;
    }
    
    /* 打开目标文件 */
    dst_fp = fopen(dst_path, "wb");
    if (!dst_fp) {
        fclose(src_fp);
        return -1;
    }
    
    /* 复制数据 */
    while ((bytes_read = fread(buffer, 1, sizeof(buffer), src_fp)) > 0) {
        if (fwrite(buffer, 1, bytes_read, dst_fp) != bytes_read) {
            fclose(src_fp);
            fclose(dst_fp);
            return -1;
        }
    }
    
    fclose(src_fp);
    fclose(dst_fp);
    
    return 0;
}
