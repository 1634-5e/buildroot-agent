/*
 * Ping监控模块
 * 对配置的目标IP执行ping并上报结果
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/time.h>
#include <arpa/inet.h>
#include <netinet/ip.h>
#include <netinet/ip_icmp.h>
#include <netdb.h>
#include "agent.h"

typedef struct {
    struct icmphdr hdr;
    char data[64];
} icmp_packet_t;

typedef struct {
    agent_context_t *ctx;
    int running;
} ping_thread_context_t;
static unsigned short checksum(void *b, int len)
{
    unsigned short *buf = (unsigned short *)b;
    unsigned int sum = 0;
    unsigned short result;

    for (sum = 0; len > 1; len -= 2) {
        sum += *buf++;
    }
    if (len == 1) {
        sum += *(unsigned char *)buf;
    }
    sum = (sum >> 16) + (sum & 0xFFFF);
    sum += (sum >> 16);
    result = ~sum;
    return result;
}

static int resolve_ip(const char *hostname, struct sockaddr_in *addr)
{
    struct addrinfo hints, *res;
    int ret;

    if (inet_aton(hostname, &addr->sin_addr) != 0) {
        return 0;
    }

    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_RAW;

    ret = getaddrinfo(hostname, NULL, &hints, &res);
    if (ret != 0) {
        LOG_ERROR("无法解析主机名: %s (%s)", hostname, gai_strerror(ret));
        return -1;
    }

    memcpy(addr, res->ai_addr, res->ai_addrlen);
    freeaddrinfo(res);
    return 0;
}

int ping_execute(const char *ip, int timeout_sec, int count, ping_result_t *result)
{
    int sock;
    struct sockaddr_in addr;
    struct timeval tv_out;
    fd_set read_set;
    int i;
    double total_time = 0.0;
    double min_time = 99999.0;
    double max_time = 0.0;
    int packets_received = 0;

    if (!result) {
        LOG_ERROR("ping_result为NULL");
        return -1;
    }

    memset(result, 0, sizeof(ping_result_t));
    strncpy(result->ip, ip, sizeof(result->ip) - 1);
    result->status = PING_STATUS_UNKNOWN;
    result->packets_sent = count;
    result->packets_received = 0;
    result->timestamp = get_timestamp_ms();

    sock = socket(AF_INET, SOCK_RAW, IPPROTO_ICMP);
    if (sock < 0) {
        LOG_ERROR("创建socket失败: %s", strerror(errno));
        result->status = PING_STATUS_UNREACHABLE;
        return -1;
    }

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    if (resolve_ip(ip, &addr) != 0) {
        close(sock);
        result->status = PING_STATUS_UNREACHABLE;
        return -1;
    }

    tv_out.tv_sec = timeout_sec;
    tv_out.tv_usec = 0;

    signal(SIGALRM, SIG_IGN);

    for (i = 0; i < count; i++) {
        icmp_packet_t packet;
        struct timeval tv_start, tv_end, tv_diff;
        int ret;
        ssize_t len;

        memset(&packet, 0, sizeof(packet));
        packet.hdr.type = ICMP_ECHO;
        packet.hdr.code = 0;
        packet.hdr.un.echo.id = getpid() & 0xFFFF;
        packet.hdr.un.echo.sequence = i;
        packet.hdr.checksum = checksum(&packet, sizeof(packet));

        gettimeofday(&tv_start, NULL);

        ret = sendto(sock, &packet, sizeof(packet), 0,
                   (struct sockaddr *)&addr, sizeof(addr));
        if (ret < 0) {
            LOG_WARN("发送ping包失败: %s", strerror(errno));
            continue;
        }

        FD_ZERO(&read_set);
        FD_SET(sock, &read_set);
        ret = select(sock + 1, &read_set, NULL, NULL, &tv_out);

        if (ret > 0) {
            char recv_buf[256];
            struct sockaddr_in from;
            socklen_t from_len = sizeof(from);
            struct iphdr *ip_hdr;
            struct icmphdr *icmp_hdr;
            size_t ip_hdr_len;

            len = recvfrom(sock, recv_buf, sizeof(recv_buf), 0,
                        (struct sockaddr *)&from, &from_len);
            if (len > 0) {
                /* 解析 IP 头 */
                ip_hdr = (struct iphdr *)recv_buf;
                ip_hdr_len = ip_hdr->ihl * 4;

                /* 防止 ip_hdr_len 下溢：确保缓冲区至少有 IP 头 */
                if (len < ip_hdr_len) {
                    LOG_WARN("接收到的包太短: len=%zd, ip_hdr_len=%zu", len, ip_hdr_len);
                    continue;
                }

                /* 检查缓冲区大小是否足够 */
                if (len < ip_hdr_len + sizeof(struct icmphdr)) {
                    LOG_WARN("接收到的包太短");
                    continue;
                }

                /* 验证 TTL 值是否合理 */
                if (ip_hdr->ttl == 0) {
                    LOG_WARN("无效的 TTL 值: %d", ip_hdr->ttl);
                    continue;
                }

                /* 验证源 IP 地址是否匹配目标 IP */
                if (from.sin_addr.s_addr != addr.sin_addr.s_addr) {
                    LOG_DEBUG("忽略来自非目标IP的响应");
                    continue;
                }


                /* 获取 ICMP 头（跳过 IP 头） */
                icmp_hdr = (struct icmphdr *)(recv_buf + ip_hdr_len);

                /* 验证是否是 ICMP Echo Reply */
                if (icmp_hdr->type != ICMP_ECHOREPLY) {
                    continue;
                }

                /* 验证是否是对我们发送的包的响应 */
                if (icmp_hdr->un.echo.id != (getpid() & 0xFFFF) ||
                    icmp_hdr->un.echo.sequence != i) {
                    continue;
                }

                gettimeofday(&tv_end, NULL);

                timersub(&tv_end, &tv_start, &tv_diff);
                double rtt = (double)tv_diff.tv_sec * 1000.0 +
                           (double)tv_diff.tv_usec / 1000.0;

                total_time += rtt;
                if (rtt < min_time) min_time = rtt;
                if (rtt > max_time) max_time = rtt;
                packets_received++;
            }
        } else if (ret == 0) {
            LOG_DEBUG("Ping超时: %s", ip);
        } else {
            LOG_WARN("select错误: %s", strerror(errno));
        }

        usleep(100000);
    }

    close(sock);

    result->packets_received = packets_received;
    result->timestamp = get_timestamp_ms();

    if (packets_received == 0) {
        result->status = PING_STATUS_TIMEOUT;
        result->avg_time = 0.0;
        result->min_time = 0.0;
        result->max_time = 0.0;
        result->packet_loss = 100.0;
    } else if (packets_received < count) {
        result->status = PING_STATUS_UNREACHABLE;
        result->avg_time = (float)(total_time / packets_received);
        result->min_time = min_time;
        result->max_time = max_time;
        result->packet_loss = (float)(count - packets_received) / count * 100.0;
    } else {
        result->status = PING_STATUS_REACHABLE;
        result->avg_time = (float)(total_time / packets_received);
        result->min_time = min_time;
        result->max_time = max_time;
        result->packet_loss = 0.0;
    }

    return 0;
}

int ping_execute_all(agent_context_t *ctx)
{
    ping_status_t status;
    int i;
    char *json;

    if (!ctx) {
        LOG_ERROR("agent_context为NULL");
        return -1;
    }

    if (!ctx->config.enable_ping || ctx->config.ping_target_count == 0) {
        return 0;
    }

    memset(&status, 0, sizeof(status));
    status.timestamp = get_timestamp_ms();
    status.result_count = ctx->config.ping_target_count;

    for (i = 0; i < ctx->config.ping_target_count && i < 16; i++) {
        const ping_target_t *target = &ctx->config.ping_targets[i];
        LOG_INFO("[DEBUG] target[%d]: ip='%s', name='%s'", i, target->ip, target->name);
        int timeout = target->timeout > 0 ? target->timeout : ctx->config.ping_timeout;
        int count = target->count > 0 ? target->count : ctx->config.ping_count;

        LOG_INFO("Ping目标: %s (timeout=%d, count=%d)", target->ip, timeout, count);
        ping_execute(target->ip, timeout, count, &status.results[i]);
    }

    json = ping_status_to_json(&status);
    if (json) {
        socket_send_json(ctx, MSG_TYPE_PING_STATUS, json);
        LOG_INFO("上报ping状态: %d个目标", status.result_count);
        free(json);
    }

    return 0;
}

char *ping_status_to_json(ping_status_t *status)
{
    if (!status) {
        return NULL;
    }

    size_t json_size = 2048 + (status->result_count * 256);
    char *json = malloc(json_size);
    if (!json) {
        LOG_ERROR("分配JSON缓冲区失败");
        return NULL;
    }

    int offset = snprintf(json, json_size,
        "{"
        "\"timestamp\":%" PRIu64 ","
        "\"results\":[",
        status->timestamp);

    for (int i = 0; i < status->result_count && i < 16; i++) {
        const ping_result_t *r = &status->results[i];
        offset += snprintf(json + offset, json_size - offset,
            "%s{\"ip\":\"%s\","
            "\"status\":%d,"
            "\"avg_time\":%.2f,"
            "\"min_time\":%.2f,"
            "\"max_time\":%.2f,"
            "\"packet_loss\":%.2f,"
            "\"packets_sent\":%d,"
            "\"packets_received\":%d,"
            "\"timestamp\":%" PRIu64 "}",
            i > 0 ? "," : "",
            r->ip,
            r->status,
            r->avg_time,
            r->min_time,
            r->max_time,
            r->packet_loss,
            r->packets_sent,
            r->packets_received,
            r->timestamp);
    }

    snprintf(json + offset, json_size - offset, "]}");

    return json;
}

void *ping_thread(void *arg)
{
    agent_context_t *ctx = (agent_context_t *)arg;

    LOG_INFO("Ping监控线程启动");

    while (ctx->running) {
        if (ctx->connected && ctx->registered) {
            if (ctx->config.enable_ping) {
                LOG_INFO("Ping执行: enable=%d, targets=%d", 
                    ctx->config.enable_ping, ctx->config.ping_target_count);
                ping_execute_all(ctx);
            } else {
                LOG_INFO("Ping未启用: enable=%d", ctx->config.enable_ping);
            }
        }

        int interval = ctx->config.ping_interval > 0 ?
                     ctx->config.ping_interval : 60;
        for (int i = 0; i < interval && ctx->running; i++) {
            sleep(1);
        }
    }

    LOG_INFO("Ping监控线程退出");
    LOG_INFO("Ping监控线程退出");
    return NULL;
}

int ping_init_from_config(agent_config_t *config)
{
    /* Ping配置已由YAML解析完成，此函数保留为兼容接口 */
    if (!config) {
        return -1;
    }
    return 0;
}

int ping_save_config(agent_config_t *config, const char *path)
{
    FILE *fp;
    int i;

    if (!config || !path) {
        return -1;
    }

    fp = fopen(path, "w");
    if (!fp) {
        LOG_ERROR("无法打开配置文件: %s", path);
        return -1;
    }

    fprintf(fp, "# Ping监控配置\n");
    fprintf(fp, "enable=%s\n", config->enable_ping ? "true" : "false");
    fprintf(fp, "interval=%d\n", config->ping_interval);
    fprintf(fp, "timeout=%d\n", config->ping_timeout);
    fprintf(fp, "count=%d\n", config->ping_count);
    fprintf(fp, "\n# Ping目标列表 (格式: IP[,名称][,间隔])\n");
    for (i = 0; i < config->ping_target_count; i++) {
        const ping_target_t *target = &config->ping_targets[i];
        fprintf(fp, "target=%s", target->ip);
        if (target->name[0] != '\0') {
            fprintf(fp, ",%s", target->name);
        }
        if (target->interval > 0) {
            fprintf(fp, ",%d", target->interval);
        }
        fprintf(fp, "\n");
    }

    fclose(fp);
    LOG_INFO("已保存ping配置: %s", path);
    return 0;
}
