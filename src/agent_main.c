/*
 * Buildroot Agent 主程序
 * 嵌入式设备远程管理Agent
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <getopt.h>
#include <pthread.h>
#include "agent.h"

/* 全局Agent上下文 */
agent_context_t *g_agent_ctx = NULL;

/* PID文件路径 */
#define PID_FILE    "/var/run/buildroot-agent.pid"

/* 信号处理 */
static void signal_handler(int sig)
{
    LOG_INFO("收到信号: %d", sig);
    
    if (g_agent_ctx) {
        g_agent_ctx->running = false;
    }
}

/* 设置信号处理 */
static void setup_signals(void)
{
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    signal(SIGHUP, signal_handler);
    signal(SIGPIPE, SIG_IGN);  /* 忽略SIGPIPE */
    signal(SIGCHLD, SIG_IGN);  /* 自动回收子进程 */
}

/* 心跳线程 */
static void *heartbeat_thread(void *arg)
{
    agent_context_t *ctx = (agent_context_t *)arg;
    
    LOG_INFO("心跳线程启动");
    
    while (ctx->running) {
        if (ctx->connected && ctx->authenticated) {
            char *heartbeat = protocol_create_heartbeat(ctx);
            if (heartbeat) {
                ws_send_json(ctx, MSG_TYPE_HEARTBEAT, heartbeat);
                LOG_DEBUG("发送心跳");
                free(heartbeat);
            }
        }
        
        sleep(ctx->config.heartbeat_interval > 0 ? 
              ctx->config.heartbeat_interval : DEFAULT_HEARTBEAT_SEC);
    }
    
    LOG_INFO("心跳线程退出");
    return NULL;
}

/* 初始化Agent */
int agent_init(const char *config_path)
{
    /* 分配上下文 */
    g_agent_ctx = calloc(1, sizeof(agent_context_t));
    if (!g_agent_ctx) {
        fprintf(stderr, "内存分配失败\n");
        return -1;
    }
    
    /* 初始化互斥锁 */
    pthread_mutex_init(&g_agent_ctx->lock, NULL);
    
    /* 加载配置 */
    const char *conf_path = config_path ? config_path : DEFAULT_CONFIG_PATH;
    if (config_load(&g_agent_ctx->config, conf_path) != 0) {
        LOG_WARN("加载配置失败，使用默认配置");
    }
    
    /* 设置日志级别 */
    set_log_level(g_agent_ctx->config.log_level);
    
    /* 打印配置 */
    config_print(&g_agent_ctx->config);
    
    /* 确保脚本目录存在 */
    mkdir_recursive(g_agent_ctx->config.script_path, 0755);
    
    /* 初始化PTY会话 */
    g_agent_ctx->max_pty_sessions = 8;
    
    LOG_INFO("Agent初始化完成");
    return 0;
}

/* 启动Agent */
int agent_start(void)
{
    if (!g_agent_ctx) {
        LOG_ERROR("Agent未初始化");
        return -1;
    }
    
    g_agent_ctx->running = true;
    
    LOG_INFO("========================================");
    LOG_INFO("  Buildroot Agent v%s", AGENT_VERSION);
    LOG_INFO("  设备ID: %s", g_agent_ctx->config.device_id);
    LOG_INFO("========================================");
    
    /* 连接到服务器 */
    if (ws_connect(g_agent_ctx) != 0) {
        LOG_ERROR("连接服务器失败");
        /* 继续运行，会自动重连 */
    }
    
    /* 启动心跳线程 */
    pthread_t hb_thread;
    if (pthread_create(&hb_thread, NULL, heartbeat_thread, g_agent_ctx) != 0) {
        LOG_ERROR("创建心跳线程失败");
    } else {
        pthread_detach(hb_thread);
    }
    
    /* 启动状态采集线程 */
    pthread_t status_thd;
    if (pthread_create(&status_thd, NULL, status_thread, g_agent_ctx) != 0) {
        LOG_ERROR("创建状态采集线程失败");
    } else {
        pthread_detach(status_thd);
    }
    
    LOG_INFO("Agent已启动");
    
    /* 主循环 */
    while (g_agent_ctx->running) {
        sleep(1);
    }
    
    LOG_INFO("Agent正在停止...");
    
    return 0;
}

/* 停止Agent */
void agent_stop(void)
{
    if (!g_agent_ctx) return;
    
    g_agent_ctx->running = false;
    
    /* 断开WebSocket连接 */
    ws_disconnect(g_agent_ctx);
    
    /* 清理PTY会话 */
    pty_cleanup_all(g_agent_ctx);
    
    /* 停止日志监控 */
    log_watch_stop_all();
    
    LOG_INFO("Agent已停止");
}

/* 清理Agent */
void agent_cleanup(void)
{
    if (!g_agent_ctx) return;
    
    /* 清理WebSocket */
    ws_cleanup();
    
    /* 销毁互斥锁 */
    pthread_mutex_destroy(&g_agent_ctx->lock);
    
    /* 释放上下文 */
    free(g_agent_ctx);
    g_agent_ctx = NULL;
    
    /* 删除PID文件 */
    remove_pid_file(PID_FILE);
    
    LOG_INFO("Agent清理完成");
}

/* 打印帮助 */
static void print_help(const char *prog)
{
    printf("Buildroot Agent v%s\n\n", AGENT_VERSION);
    printf("用法: %s [选项]\n\n", prog);
    printf("选项:\n");
    printf("  -c, --config <path>   指定配置文件路径 (默认: %s)\n", DEFAULT_CONFIG_PATH);
    printf("  -s, --server <url>    指定服务器地址\n");
    printf("  -t, --token <token>   指定认证Token\n");
    printf("  -d, --daemon          以守护进程方式运行\n");
    printf("  -v, --verbose         详细输出 (debug级别)\n");
    printf("  -g, --generate        生成默认配置文件\n");
    printf("  -h, --help            显示帮助信息\n");
    printf("  -V, --version         显示版本信息\n");
    printf("\n");
    printf("示例:\n");
    printf("  %s -c /etc/agent.conf -d\n", prog);
    printf("  %s -s wss://server.com/agent -t mytoken\n", prog);
    printf("\n");
}

/* 打印版本 */
static void print_version(void)
{
    printf("Buildroot Agent v%s\n", AGENT_VERSION);
    printf("Build: %s %s\n", __DATE__, __TIME__);
}

/* 主函数 */
int main(int argc, char *argv[])
{
    const char *config_path = NULL;
    const char *server_url = NULL;
    const char *auth_token = NULL;
    bool daemon_mode = false;
    bool verbose = false;
    bool generate_config = false;
    
    /* 解析命令行参数 */
    static struct option long_options[] = {
        {"config",   required_argument, 0, 'c'},
        {"server",   required_argument, 0, 's'},
        {"token",    required_argument, 0, 't'},
        {"daemon",   no_argument,       0, 'd'},
        {"verbose",  no_argument,       0, 'v'},
        {"generate", no_argument,       0, 'g'},
        {"help",     no_argument,       0, 'h'},
        {"version",  no_argument,       0, 'V'},
        {0, 0, 0, 0}
    };
    
    int opt;
    while ((opt = getopt_long(argc, argv, "c:s:t:dvghV", long_options, NULL)) != -1) {
        switch (opt) {
        case 'c':
            config_path = optarg;
            break;
        case 's':
            server_url = optarg;
            break;
        case 't':
            auth_token = optarg;
            break;
        case 'd':
            daemon_mode = true;
            break;
        case 'v':
            verbose = true;
            break;
        case 'g':
            generate_config = true;
            break;
        case 'h':
            print_help(argv[0]);
            return 0;
        case 'V':
            print_version();
            return 0;
        default:
            print_help(argv[0]);
            return 1;
        }
    }
    
    /* 生成默认配置文件 */
    if (generate_config) {
        agent_config_t config;
        config_set_defaults(&config);
        
        const char *path = config_path ? config_path : DEFAULT_CONFIG_PATH;
        if (config_save(&config, path) == 0) {
            printf("配置文件已生成: %s\n", path);
            return 0;
        } else {
            fprintf(stderr, "生成配置文件失败\n");
            return 1;
        }
    }
    
    /* 检查是否已运行 */
    if (is_process_running(PID_FILE)) {
        fprintf(stderr, "Agent已在运行中\n");
        return 1;
    }
    
    /* 守护进程模式 */
    if (daemon_mode) {
        printf("以守护进程模式启动...\n");
        if (daemonize() != 0) {
            fprintf(stderr, "守护进程化失败\n");
            return 1;
        }
        
        /* 设置日志文件 */
        set_log_file("/var/log/buildroot-agent.log");
    }
    
    /* 写入PID文件 */
    write_pid_file(PID_FILE);
    
    /* 设置信号处理 */
    setup_signals();
    
    /* 初始化Agent */
    if (agent_init(config_path) != 0) {
        fprintf(stderr, "Agent初始化失败\n");
        return 1;
    }
    
    /* 覆盖命令行参数 */
    if (server_url) {
        strncpy(g_agent_ctx->config.server_url, server_url, 
                sizeof(g_agent_ctx->config.server_url) - 1);
    }
    if (auth_token) {
        strncpy(g_agent_ctx->config.auth_token, auth_token,
                sizeof(g_agent_ctx->config.auth_token) - 1);
    }
    if (verbose) {
        g_agent_ctx->config.log_level = LOG_LEVEL_DEBUG;
        set_log_level(LOG_LEVEL_DEBUG);
    }
    
    /* 启动Agent */
    int ret = agent_start();
    
    /* 停止并清理 */
    agent_stop();
    agent_cleanup();
    
    return ret;
}
