/*
 * 系统状态采集模块
 * 从/proc文件系统读取系统状态信息
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/sysinfo.h>
#include <sys/statvfs.h>
#include <sys/utsname.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <ifaddrs.h>

#include <pthread.h>

#include <dirent.h>

#include "agent.h"

/* 上一次的CPU时间，用于计算CPU使用率 */
static unsigned long long prev_total = 0;
static unsigned long long prev_idle = 0;
static unsigned long long prev_user = 0;
static unsigned long long prev_system = 0;

/* 上一次的网络统计 */
static long prev_rx_bytes = 0;
static long prev_tx_bytes = 0;

/* 读取CPU使用率和详细信息 */
static float get_cpu_usage(float *cpu_user, float *cpu_system)
{
    FILE *fp = fopen("/proc/stat", "r");
    if (!fp) {
        *cpu_user = 0.0;
        *cpu_system = 0.0;
        return 0.0;
    }
    
    char line[256];
    unsigned long long user, nice, system, idle, iowait, irq, softirq, steal;
    
    if (fgets(line, sizeof(line), fp) == NULL) {
        fclose(fp);
        *cpu_user = 0.0;
        *cpu_system = 0.0;
        return 0.0;
    }
    fclose(fp);
    
    sscanf(line, "cpu %llu %llu %llu %llu %llu %llu %llu %llu",
           &user, &nice, &system, &idle, &iowait, &irq, &softirq, &steal);
    
    unsigned long long total = user + nice + system + idle + iowait + irq + softirq + steal;
    unsigned long long idle_time = idle + iowait;
    unsigned long long user_time = user + nice;
    unsigned long long system_time = system + irq + softirq;
    
    float cpu_usage = 0.0;
    float cpu_user_usage = 0.0;
    float cpu_system_usage = 0.0;
    
    if (prev_total > 0) {
        unsigned long long total_diff = total - prev_total;
        unsigned long long idle_diff = idle_time - prev_idle;
        unsigned long long user_diff = user_time - prev_user;
        unsigned long long system_diff = system_time - prev_system;
        
        if (total_diff > 0) {
            cpu_usage = 100.0 * (1.0 - (float)idle_diff / (float)total_diff);
        }
        
        if (total_diff > 0) {
            cpu_user_usage = 100.0 * (float)user_diff / (float)total_diff;
            cpu_system_usage = 100.0 * (float)system_diff / (float)total_diff;
        }
    }
    
    prev_total = total;
    prev_idle = idle_time;
    prev_user = user_time;
    prev_system = system_time;
    
    *cpu_user = cpu_user_usage;
    *cpu_system = cpu_system_usage;
    
    return cpu_usage;
}

/* 读取内存信息 */
static void get_memory_info(float *total, float *used, float *free_mem)
{
    FILE *fp = fopen("/proc/meminfo", "r");
    if (!fp) {
        *total = *used = *free_mem = 0;
        return;
    }
    
    char line[256];
    unsigned long mem_total = 0, mem_free = 0, mem_available = 0;
    unsigned long buffers = 0, cached = 0;
    
    while (fgets(line, sizeof(line), fp)) {
        if (strncmp(line, "MemTotal:", 9) == 0) {
            sscanf(line + 9, "%lu", &mem_total);
        } else if (strncmp(line, "MemFree:", 8) == 0) {
            sscanf(line + 8, "%lu", &mem_free);
        } else if (strncmp(line, "MemAvailable:", 13) == 0) {
            sscanf(line + 13, "%lu", &mem_available);
        } else if (strncmp(line, "Buffers:", 8) == 0) {
            sscanf(line + 8, "%lu", &buffers);
        } else if (strncmp(line, "Cached:", 7) == 0) {
            sscanf(line + 7, "%lu", &cached);
        }
    }
    fclose(fp);
    
    /* 转换为MB */
    *total = (float)mem_total / 1024.0;
    *free_mem = (float)(mem_available > 0 ? mem_available : mem_free + buffers + cached) / 1024.0;
    *used = *total - *free_mem;
}

/* 读取磁盘信息 */
static void get_disk_info(float *total, float *used, const char *path)
{
    struct statvfs stat;
    
    if (statvfs(path ? path : "/", &stat) != 0) {
        *total = *used = 0;
        return;
    }
    
    unsigned long long total_bytes = (unsigned long long)stat.f_blocks * stat.f_frsize;
    unsigned long long free_bytes = (unsigned long long)stat.f_bfree * stat.f_frsize;
    
    *total = (float)total_bytes / (1024.0 * 1024.0);
    *used = (float)(total_bytes - free_bytes) / (1024.0 * 1024.0);
}

/* 读取系统负载 */
static void get_load_avg(float *load1, float *load5, float *load15)
{
    FILE *fp = fopen("/proc/loadavg", "r");
    if (!fp) {
        *load1 = *load5 = *load15 = 0;
        return;
    }
    
    fscanf(fp, "%f %f %f", load1, load5, load15);
    fclose(fp);
}

/* 读取运行时间 */
static uint32_t get_uptime(void)
{
    struct sysinfo info;
    if (sysinfo(&info) == 0) {
        return (uint32_t)info.uptime;
    }
    return 0;
}

/* 获取网络接口信息 */
static void get_network_info(char *ip_addr, char *mac_addr, long *rx_bytes, long *tx_bytes)
{
    struct ifaddrs *ifaddr, *ifa;
    
    ip_addr[0] = '\0';
    mac_addr[0] = '\0';
    *rx_bytes = 0;
    *tx_bytes = 0;
    
    if (getifaddrs(&ifaddr) == -1) {
        return;
    }
    
    /* 查找第一个非lo的网络接口 */
    for (ifa = ifaddr; ifa != NULL; ifa = ifa->ifa_next) {
        if (ifa->ifa_addr == NULL) continue;
        if (strcmp(ifa->ifa_name, "lo") == 0) continue;
        
        /* 获取IP地址 */
        if (ifa->ifa_addr->sa_family == AF_INET) {
            struct sockaddr_in *addr = (struct sockaddr_in *)ifa->ifa_addr;
            inet_ntop(AF_INET, &addr->sin_addr, ip_addr, 32);
            
            /* 获取MAC地址 */
            int sock = socket(AF_INET, SOCK_DGRAM, 0);
            if (sock >= 0) {
                struct ifreq ifr;
                strncpy(ifr.ifr_name, ifa->ifa_name, IFNAMSIZ - 1);
                if (ioctl(sock, SIOCGIFHWADDR, &ifr) == 0) {
                    unsigned char *mac = (unsigned char *)ifr.ifr_hwaddr.sa_data;
                    snprintf(mac_addr, 20, "%02X:%02X:%02X:%02X:%02X:%02X",
                             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
                }
                close(sock);
            }
            break;
        }
    }
    
    freeifaddrs(ifaddr);
    
    /* 读取网络统计 */
    FILE *fp = fopen("/proc/net/dev", "r");
    if (fp) {
        char line[512];
        /* 跳过前两行头部 */
        fgets(line, sizeof(line), fp);
        fgets(line, sizeof(line), fp);
        
        while (fgets(line, sizeof(line), fp)) {
            char iface[32];
            long rx, tx;
            sscanf(line, "%31[^:]:%ld %*d %*d %*d %*d %*d %*d %*d %ld",
                   iface, &rx, &tx);
            
            /* 去除空格 */
            char *p = iface;
            while (*p == ' ') p++;
            
            if (strcmp(p, "lo") != 0) {
                *rx_bytes += rx;
                *tx_bytes += tx;
            }
        }
        fclose(fp);
    }
}

/* 获取主机名 */
static void get_hostname(char *hostname, size_t len)
{
    if (gethostname(hostname, len) != 0) {
        strncpy(hostname, "unknown", len);
    }
}

/* 获取内核版本 */
static void get_kernel_version(char *version, size_t len)
{
    struct utsname uts;
    if (uname(&uts) == 0) {
        snprintf(version, len, "%s %s", uts.sysname, uts.release);
    } else {
        strncpy(version, "unknown", len);
    }
}

/* 进程信息结构 */

typedef struct {

    int pid;

    char name[64];

    char state;         /* R/S/D/Z/T */

    float cpu;          /* CPU使用率% */

    unsigned long mem;  /* 内存 KB */

    unsigned long utime;

    unsigned long stime;

    unsigned long long starttime;

    char time_str[16];  /* 运行时间字符串 */

} proc_info_t;



/* 上一次进程CPU时间缓存 (用于计算CPU%) */

#define MAX_PROC_CACHE 256

static struct {

    int pid;

    unsigned long utime;

    unsigned long stime;

} prev_proc_times[MAX_PROC_CACHE];

static int prev_proc_count = 0;

static unsigned long long prev_total_cpu = 0;



/* 获取进程列表 (返回进程数量) */

static int get_process_list(proc_info_t *procs, int max_procs)

{

    DIR *dir = opendir("/proc");

    if (!dir) return 0;



    /* 先读取当前总CPU时间 */

    unsigned long long total_cpu = 0;

    {

        FILE *fp = fopen("/proc/stat", "r");

        if (fp) {

            char line[256];

            if (fgets(line, sizeof(line), fp)) {

                unsigned long long u, n, s, i, io, ir, si, st;

                sscanf(line, "cpu %llu %llu %llu %llu %llu %llu %llu %llu",

                       &u, &n, &s, &i, &io, &ir, &si, &st);

                total_cpu = u + n + s + i + io + ir + si + st;

            }

            fclose(fp);

        }

    }



    unsigned long long cpu_diff = total_cpu - prev_total_cpu;

    if (cpu_diff == 0) cpu_diff = 1;



    /* 获取系统运行时间(秒) */

    float uptime_sec = 0;

    {

        FILE *fp = fopen("/proc/uptime", "r");

        if (fp) {

            fscanf(fp, "%f", &uptime_sec);

            fclose(fp);

        }

    }



    long clk_tck = sysconf(_SC_CLK_TCK);

    if (clk_tck <= 0) clk_tck = 100;



    int count = 0;

    struct dirent *entry;



    while ((entry = readdir(dir)) != NULL && count < max_procs) {

        /* 只处理数字目录名(即PID) */

        int pid = atoi(entry->d_name);

        if (pid <= 0) continue;



        char path[128];

        snprintf(path, sizeof(path), "/proc/%d/stat", pid);



        FILE *fp = fopen(path, "r");

        if (!fp) continue;



        char line[512];

        if (!fgets(line, sizeof(line), fp)) {

            fclose(fp);

            continue;

        }

        fclose(fp);



        /* 解析 /proc/[pid]/stat */

        /* 格式: pid (comm) state ppid ... utime stime ... starttime ... rss ... */

        char *comm_start = strchr(line, '(');

        char *comm_end = strrchr(line, ')');

        if (!comm_start || !comm_end) continue;



        proc_info_t *p = &procs[count];

        p->pid = pid;



        /* 提取进程名 */

        int name_len = comm_end - comm_start - 1;

        if (name_len > 63) name_len = 63;

        strncpy(p->name, comm_start + 1, name_len);

        p->name[name_len] = '\0';



        /* 解析comm后面的字段 */

        char *rest = comm_end + 2; /* 跳过 ") " */

        char state;

        int ppid;

        unsigned long utime, stime;

        long rss;

        unsigned long long starttime;



        /* state(1) ppid(2) pgrp(3) session(4) tty_nr(5) tpgid(6) flags(7)

           minflt(8) cminflt(9) majflt(10) cmajflt(11) utime(12) stime(13)

           cutime(14) cstime(15) priority(16) nice(17) num_threads(18)

           itrealvalue(19) starttime(20) vsize(21) rss(22) */

        int n = sscanf(rest,

            "%c %d %*d %*d %*d %*d %*u "

            "%*u %*u %*u %*u %lu %lu "

            "%*d %*d %*d %*d %*d "

            "%*d %llu %*u %ld",

            &state, &ppid, &utime, &stime, &starttime, &rss);



        if (n < 6) continue;



        p->state = state;

        p->utime = utime;

        p->stime = stime;

        p->starttime = starttime;

        p->mem = (rss * 4); /* 页面大小通常4KB */



        /* 计算CPU使用率: 与上次采样的差值 */

        p->cpu = 0.0;

        for (int i = 0; i < prev_proc_count; i++) {

            if (prev_proc_times[i].pid == pid) {

                unsigned long d_utime = utime - prev_proc_times[i].utime;

                unsigned long d_stime = stime - prev_proc_times[i].stime;

                p->cpu = 100.0 * (float)(d_utime + d_stime) / (float)cpu_diff;

                if (p->cpu > 100.0) p->cpu = 100.0;

                if (p->cpu < 0.0) p->cpu = 0.0;

                break;

            }

        }



        /* 计算运行时间字符串 */

        float proc_uptime = uptime_sec - ((float)starttime / (float)clk_tck);

        if (proc_uptime < 0) proc_uptime = 0;

        int hours = (int)(proc_uptime / 3600);

        int mins = (int)((proc_uptime - hours * 3600) / 60);

        int secs = (int)(proc_uptime) % 60;

        if (hours > 0) {

            snprintf(p->time_str, sizeof(p->time_str), "%d:%02d:%02d", hours, mins, secs);

        } else {

            snprintf(p->time_str, sizeof(p->time_str), "%d:%02d", mins, secs);

        }



        count++;

    }

    closedir(dir);



    /* 更新缓存 */

    prev_proc_count = count < MAX_PROC_CACHE ? count : MAX_PROC_CACHE;

    for (int i = 0; i < prev_proc_count; i++) {

        prev_proc_times[i].pid = procs[i].pid;

        prev_proc_times[i].utime = procs[i].utime;

        prev_proc_times[i].stime = procs[i].stime;

    }

    prev_total_cpu = total_cpu;



    /* 按CPU使用率降序排序 */

    for (int i = 0; i < count - 1; i++) {

        for (int j = i + 1; j < count; j++) {

            if (procs[j].cpu > procs[i].cpu) {

                proc_info_t tmp = procs[i];

                procs[i] = procs[j];

                procs[j] = tmp;

            }

        }

    }



    return count;

}



/* 采集系统状态 */

int status_collect(system_status_t *status)
{
    if (!status) return -1;
    
    memset(status, 0, sizeof(system_status_t));
    
    /* CPU使用率 (获取详细信息) */
    float cpu_user, cpu_system;
    status->cpu_usage = get_cpu_usage(&cpu_user, &cpu_system);
    status->cpu_user = cpu_user;
    status->cpu_system = cpu_system;
    
    /* CPU核心数 */
    status->cpu_cores = sysconf(_SC_NPROCESSORS_ONLN);
    
    /* 内存信息 */
    get_memory_info(&status->mem_total, &status->mem_used, &status->mem_free);
    
    /* 磁盘信息 */
    get_disk_info(&status->disk_total, &status->disk_used, "/");
    
    /* 系统负载 */
    get_load_avg(&status->load_1min, &status->load_5min, &status->load_15min);
    
    /* 运行时间 */
    status->uptime = get_uptime();
    
    /* 网络信息 */
    long rx_bytes, tx_bytes;
    get_network_info(status->ip_addr, status->mac_addr, &rx_bytes, &tx_bytes);
    
    /* 计算网络速率 (bytes/s，假设1秒采集一次) */
    if (prev_rx_bytes > 0) {
        status->net_rx_bytes = rx_bytes - prev_rx_bytes;
        status->net_tx_bytes = tx_bytes - prev_tx_bytes;
    }
    prev_rx_bytes = rx_bytes;
    prev_tx_bytes = tx_bytes;
    
    /* 主机名和内核版本 */
    get_hostname(status->hostname, sizeof(status->hostname));
    get_kernel_version(status->kernel_version, sizeof(status->kernel_version));
    
    return 0;
}

/* 将状态转换为JSON (含进程列表) */
char *status_to_json(system_status_t *status)
{
    if (!status) return NULL;
    
    /* 采集进程列表 */
    #define MAX_PROCS 128
    #define TOP_N 30
    static proc_info_t procs[MAX_PROCS];
    int proc_count = get_process_list(procs, MAX_PROCS);
    int top_count = proc_count < TOP_N ? proc_count : TOP_N;
    
    /* 计算所需缓冲区大小: 基础字段~1K + 每个进程~150字节 */
    size_t json_size = 2048 + (top_count * 160);
    char *json = malloc(json_size);
    if (!json) return NULL;
    
    int offset = snprintf(json, json_size,
        "{"
        "\"cpu_usage\":%.2f,"
        "\"cpu_cores\":%d,"
        "\"cpu_user\":%.2f,"
        "\"cpu_system\":%.2f,"
        "\"mem_total\":%.2f,"
        "\"mem_used\":%.2f,"
        "\"mem_free\":%.2f,"
        "\"disk_total\":%.2f,"
        "\"disk_used\":%.2f,"
        "\"load_1min\":%.2f,"
        "\"load_5min\":%.2f,"
        "\"load_15min\":%.2f,"
        "\"uptime\":%u,"
        "\"net_rx_bytes\":%d,"
        "\"net_tx_bytes\":%d,"
        "\"hostname\":\"%s\","
        "\"kernel_version\":\"%s\","
        "\"ip_addr\":\"%s\","
        "\"mac_addr\":\"%s\","
        "\"timestamp\":%" PRIu64 ","
        "\"proc_total\":%d,"
        "\"processes\":[",
        status->cpu_usage,
        status->cpu_cores,
        status->cpu_user,
        status->cpu_system,
        status->mem_total,
        status->mem_used,
        status->mem_free,
        status->disk_total,
        status->disk_used,
        status->load_1min,
        status->load_5min,
        status->load_15min,
        status->uptime,
        status->net_rx_bytes,
        status->net_tx_bytes,
        status->hostname,
        status->kernel_version,
        status->ip_addr,
        status->mac_addr,
        get_timestamp_ms(),
        proc_count
    );
    
    /* 追加进程列表 JSON */
    for (int i = 0; i < top_count && offset < (int)json_size - 200; i++) {
        /* 转义进程名中的特殊字符 */
        char safe_name[128];
        int si = 0;
        for (int j = 0; procs[i].name[j] && si < 120; j++) {
            char c = procs[i].name[j];
            if (c == '"' || c == '\\') {
                safe_name[si++] = '\\';
            }
            safe_name[si++] = c;
        }
        safe_name[si] = '\0';
        
        offset += snprintf(json + offset, json_size - offset,
            "%s{\"pid\":%d,\"name\":\"%s\",\"state\":\"%c\","
            "\"cpu\":%.1f,\"mem\":%lu,\"time\":\"%s\"}",
            i > 0 ? "," : "",
            procs[i].pid,
            safe_name,
            procs[i].state,
            procs[i].cpu,
            procs[i].mem,
            procs[i].time_str
        );
    }
    
    /* 闭合 JSON */
    snprintf(json + offset, json_size - offset, "]}");
    
    return json;
}

/* 状态上报线程 */
void *status_thread(void *arg)
{
    agent_context_t *ctx = (agent_context_t *)arg;
    
    LOG_INFO("状态采集线程启动");
    
    while (ctx->running) {
        /* 等待连接和注册 */
        if (ctx->connected && ctx->registered) {
            system_status_t status;

            if (status_collect(&status) == 0) {
                char *json = status_to_json(&status);
                if (json) {
                    socket_send_json(ctx, MSG_TYPE_SYSTEM_STATUS, json);
                    LOG_DEBUG("上报系统状态: CPU=%.1f%%, MEM=%.1f/%.1fMB",
                              status.cpu_usage, status.mem_used, status.mem_total);
                    free(json);
                }
            }
        }
        
        /* 分段sleep，每1秒检查一次停止标志 */
        int sleep_time = ctx->config.status_interval > 0 ? 
                        ctx->config.status_interval : 60;
        for (int i = 0; i < sleep_time && ctx->running; i++) {
            sleep(1);
        }
    }
    
    LOG_INFO("状态采集线程退出");
    return NULL;
}
