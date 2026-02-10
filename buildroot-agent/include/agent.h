/*
 * Buildroot Agent - Main Header
 * 嵌入式设备远程管理Agent
 * 
 * 功能:
 * - 系统状态采集上报
 * - 日志文件上报
 * - 脚本下发执行
 * - 交互式Shell (PTY)
 */

#ifndef AGENT_H
#define AGENT_H

#include <stdint.h>
#include <stdbool.h>
#include <pthread.h>
#include <sys/types.h>
#include <inttypes.h>

/* 版本信息 */
#define AGENT_VERSION       "1.0.0"
#define AGENT_NAME          "buildroot-agent"

/* 默认配置 */
#define DEFAULT_SERVER_URL      "ws://127.0.0.1:8765/agent"
#define DEFAULT_HEARTBEAT_SEC   30
#define DEFAULT_RECONNECT_SEC   5
#define DEFAULT_LOG_PATH        "/var/log"
#define DEFAULT_SCRIPT_PATH     "/tmp/agent_scripts"
#define DEFAULT_CONFIG_PATH     "/etc/agent/agent.conf"

/* 消息类型定义 */
typedef enum {
    MSG_TYPE_HEARTBEAT      = 0x01,     /* 心跳 */
    MSG_TYPE_SYSTEM_STATUS  = 0x02,     /* 系统状态 */
    MSG_TYPE_LOG_UPLOAD     = 0x03,     /* 日志上传 */
    MSG_TYPE_SCRIPT_RECV    = 0x04,     /* 接收脚本 */
    MSG_TYPE_SCRIPT_RESULT  = 0x05,     /* 脚本执行结果 */
    MSG_TYPE_PTY_CREATE     = 0x10,     /* 创建PTY会话 */
    MSG_TYPE_PTY_DATA       = 0x11,     /* PTY数据 */
    MSG_TYPE_PTY_RESIZE     = 0x12,     /* PTY窗口大小调整 */
    MSG_TYPE_PTY_CLOSE      = 0x13,     /* 关闭PTY会话 */
    MSG_TYPE_FILE_REQUEST   = 0x20,     /* 文件请求 */
    MSG_TYPE_FILE_DATA      = 0x21,     /* 文件数据 */
    MSG_TYPE_FILE_LIST_REQUEST = 0x22,  /* 文件列表请求 */
    MSG_TYPE_FILE_LIST_RESPONSE = 0x23, /* 文件列表响应 */
    MSG_TYPE_DOWNLOAD_PACKAGE = 0x24,   /* 打包下载响应/请求 */
    MSG_TYPE_CMD_REQUEST    = 0x30,     /* 命令请求 */
    MSG_TYPE_CMD_RESPONSE   = 0x31,     /* 命令响应 */
    MSG_TYPE_DEVICE_LIST    = 0x50,     /* 设备列表更新 */
    MSG_TYPE_AUTH           = 0xF0,     /* 认证 */
    MSG_TYPE_AUTH_RESULT    = 0xF1,     /* 认证结果 */
} msg_type_t;

/* 系统状态结构 */
typedef struct {
    float cpu_usage;            /* CPU使用率 */
    int cpu_cores;              /* CPU核心数 */
    float cpu_user;             /* 用户态CPU使用率 */
    float cpu_system;           /* 系统态CPU使用率 */
    float mem_total;            /* 总内存 (MB) */
    float mem_used;             /* 已用内存 (MB) */
    float mem_free;             /* 空闲内存 (MB) */
    float disk_total;           /* 磁盘总量 (MB) */
    float disk_used;            /* 磁盘已用 (MB) */
    float load_1min;            /* 1分钟负载 */
    float load_5min;            /* 5分钟负载 */
    float load_15min;           /* 15分钟负载 */
    uint32_t uptime;            /* 运行时间 (秒) */
    int32_t net_rx_bytes;       /* 网络接收字节 */
    int32_t net_tx_bytes;       /* 网络发送字节 */
    char hostname[64];          /* 主机名 */
    char kernel_version[64];    /* 内核版本 */
    char ip_addr[32];           /* IP地址 */
    char mac_addr[20];          /* MAC地址 */
} system_status_t;

/* Agent配置结构 */
typedef struct {
    char server_url[256];       /* WebSocket服务器地址 */
    char device_id[64];         /* 设备ID */
    char auth_token[128];       /* 认证Token */
    int heartbeat_interval;     /* 心跳间隔 (秒) */
    int reconnect_interval;     /* 重连间隔 (秒) */
    int status_interval;        /* 状态上报间隔 (秒) */
    char log_path[256];         /* 日志目录 */
    char script_path[256];      /* 脚本存放目录 */
    bool enable_pty;            /* 是否启用PTY */
    bool enable_script;         /* 是否启用脚本执行 */
    int log_level;              /* 日志级别 */
} agent_config_t;

/* PTY会话结构 */
typedef struct {
    int session_id;             /* 会话ID */
    int master_fd;              /* PTY master fd */
    pid_t child_pid;            /* 子进程PID */
    pthread_t read_thread;      /* 读取线程 */
    bool active;                /* 是否活跃 */
    int rows;                   /* 终端行数 */
    int cols;                   /* 终端列数 */
} pty_session_t;

/* Agent上下文结构 */
typedef struct {
    agent_config_t config;      /* 配置 */
    void *ws_client;            /* WebSocket客户端 */
    bool connected;             /* 连接状态 */
    bool running;               /* 运行状态 */
    bool authenticated;         /* 认证状态 */
    pthread_mutex_t lock;       /* 互斥锁 */
    pty_session_t *pty_sessions;/* PTY会话数组 */
    int pty_session_count;      /* PTY会话数量 */
    int max_pty_sessions;       /* 最大PTY会话数 */
} agent_context_t;

/* 全局Agent上下文 */
extern agent_context_t *g_agent_ctx;

/* 平台兼容性定义 */
#ifndef PRIu64
#define PRIu64 "lu"
#endif

/* 函数声明 */

/* agent_main.c */
int agent_init(const char *config_path);
int agent_start(void);
void agent_stop(void);
void agent_cleanup(void);

/* agent_config.c */
int config_load(agent_config_t *config, const char *path);
int config_save(agent_config_t *config, const char *path);
void config_set_defaults(agent_config_t *config);
void config_print(agent_config_t *config);

/* agent_websocket.c */
int ws_connect(agent_context_t *ctx);
void ws_disconnect(agent_context_t *ctx);
int ws_send_message(agent_context_t *ctx, msg_type_t type, const char *data, size_t len);
int ws_send_json(agent_context_t *ctx, msg_type_t type, const char *json);
void ws_cleanup(void);

/* agent_status.c */
int status_collect(system_status_t *status);
char *status_to_json(system_status_t *status);
void *status_thread(void *arg);

/* agent_log.c */
int log_upload_file(agent_context_t *ctx, const char *filepath);
int log_tail_file(agent_context_t *ctx, const char *filepath, int lines);
int log_watch_start(agent_context_t *ctx, const char *filepath);
void log_watch_stop(agent_context_t *ctx, const char *filepath);
void log_watch_stop_all(void);
int log_list_files(agent_context_t *ctx, const char *filepath);

/* agent_script.c */
int script_save(const char *script_id, const char *content, const char *path);
int script_execute(agent_context_t *ctx, const char *script_id, const char *script_path);
int script_execute_inline(agent_context_t *ctx, const char *script_id, const char *content);
int script_list(agent_context_t *ctx);

/* agent_pty.c */
int pty_list_sessions(agent_context_t *ctx);

/* agent_pty.c */
int pty_create_session(agent_context_t *ctx, int session_id, int rows, int cols);
int pty_write_data(agent_context_t *ctx, int session_id, const char *data, size_t len);
int pty_resize(agent_context_t *ctx, int session_id, int rows, int cols);
int pty_close_session(agent_context_t *ctx, int session_id);
void pty_cleanup_all(agent_context_t *ctx);

/* agent_protocol.c */
int protocol_handle_message(agent_context_t *ctx, const char *data, size_t len);
char *protocol_create_auth_msg(agent_context_t *ctx);
char *protocol_create_heartbeat(agent_context_t *ctx);

/* agent_util.c */
void agent_log(int level, const char *fmt, ...);
void set_log_level(int level);
int set_log_file(const char *path);
char *read_file_content(const char *path, size_t *size);
int write_file_content(const char *path, const char *content, size_t size);
char *get_device_id(void);
uint64_t get_timestamp_ms(void);
int mkdir_recursive(const char *path, mode_t mode);
bool file_exists(const char *path);
long get_file_size(const char *path);
void safe_strncpy(char *dest, const char *src, size_t size);
char *str_trim(char *str);
int daemonize(void);
int write_pid_file(const char *path);
void remove_pid_file(const char *path);
bool is_process_running(const char *pid_file);

/* 日志级别 */
#define LOG_LEVEL_DEBUG     0
#define LOG_LEVEL_INFO      1
#define LOG_LEVEL_WARN      2
#define LOG_LEVEL_ERROR     3

#define LOG_DEBUG(fmt, ...) agent_log(LOG_LEVEL_DEBUG, fmt, ##__VA_ARGS__)
#define LOG_INFO(fmt, ...)  agent_log(LOG_LEVEL_INFO, fmt, ##__VA_ARGS__)
#define LOG_WARN(fmt, ...)  agent_log(LOG_LEVEL_WARN, fmt, ##__VA_ARGS__)
#define LOG_ERROR(fmt, ...) agent_log(LOG_LEVEL_ERROR, fmt, ##__VA_ARGS__)

#endif /* AGENT_H */
