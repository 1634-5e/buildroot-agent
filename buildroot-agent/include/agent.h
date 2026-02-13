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
#define DEFAULT_SERVER_ADDR     "127.0.0.1:8766"
#define DEFAULT_HEARTBEAT_SEC   30
#define DEFAULT_RECONNECT_SEC   5
#define DEFAULT_LOG_PATH        "/var/log"
#define DEFAULT_SCRIPT_PATH     "/tmp/agent_scripts"
#define DEFAULT_CONFIG_PATH     "/etc/agent/agent.conf"

/* 消息协议 */
#define MESSAGE_HEADER_SIZE 3     /* msg_type(1) + length(2) */
#define MAX_MESSAGE_SIZE 65535     /* 最大消息大小 */

/* 更新相关默认配置 */
#define DEFAULT_UPDATE_CHECK_INTERVAL   86400      /* 24小时 */
#define DEFAULT_UPDATE_CHANNEL          "stable"
#define DEFAULT_UPDATE_TEMP_PATH       "/var/lib/agent/temp"
#define DEFAULT_UPDATE_BACKUP_PATH     "/var/lib/agent/backup"
#define DEFAULT_UPDATE_ROLLBACK_TIMEOUT 300        /* 5分钟 */
#define DEFAULT_DOWNLOAD_TIMEOUT       1800       /* 30分钟 */
#define DEFAULT_MAX_DOWNLOAD_SPEED    1048576    /* 1MB/s */

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
    MSG_TYPE_FILE_DOWNLOAD_REQUEST = 0x25,  /* TCP下载请求 */
    MSG_TYPE_FILE_DOWNLOAD_DATA = 0x26,    /* TCP下载数据 */
    MSG_TYPE_FILE_DOWNLOAD_CONTROL = 0x27, /* TCP下载控制 */
    MSG_TYPE_CMD_REQUEST    = 0x30,     /* 命令请求 */
    MSG_TYPE_CMD_RESPONSE   = 0x31,     /* 命令响应 */
    MSG_TYPE_DEVICE_LIST    = 0x50,     /* 设备列表更新 */
    MSG_TYPE_AUTH           = 0xF0,     /* 认证 */
    MSG_TYPE_AUTH_RESULT    = 0xF1,     /* 认证结果 */
    
    /* 更新管理消息 */
    MSG_TYPE_UPDATE_CHECK         = 0x60,   /* 检查更新请求 */
    MSG_TYPE_UPDATE_INFO          = 0x61,   /* 更新信息响应 */
    MSG_TYPE_UPDATE_DOWNLOAD      = 0x62,   /* 请求下载更新包 */
    MSG_TYPE_UPDATE_PROGRESS      = 0x63,   /* 上报下载进度 */
    MSG_TYPE_UPDATE_APPROVE       = 0x64,   /* 服务器批准下载（提供URL）*/
    MSG_TYPE_UPDATE_COMPLETE       = 0x65,   /* 更新完成通知 */
    MSG_TYPE_UPDATE_ERROR         = 0x66,   /* 更新错误通知 */
    MSG_TYPE_UPDATE_ROLLBACK      = 0x67,   /* 回滚通知 */
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

/* 更新状态枚举 */
typedef enum {
    UPDATE_STATUS_IDLE             = 0,
    UPDATE_STATUS_CHECKING         = 1,
    UPDATE_STATUS_DOWNLOADING       = 2,
    UPDATE_STATUS_VERIFYING         = 3,
    UPDATE_STATUS_BACKING_UP        = 4,
    UPDATE_STATUS_INSTALLING        = 5,
    UPDATE_STATUS_RESTARTING        = 6,
    UPDATE_STATUS_COMPLETE         = 7,
    UPDATE_STATUS_FAILED           = 8,
    UPDATE_STATUS_ROLLING_BACK      = 9,
    UPDATE_STATUS_ROLLBACK_COMPLETE = 10,
} update_status_t;

/* 更新信息结构 */
typedef struct {
    bool has_update;                    /* 是否有新版本 */
    char current_version[32];            /* 当前版本 */
    char latest_version[32];             /* 最新版本 */
    int64_t version_code;               /* 版本号（用于比较）*/
    int64_t file_size;                  /* 文件大小（字节）*/
    char download_url[512];             /* 下载URL */
    char md5_checksum[64];             /* MD5 校验和 */
    char sha256_checksum[128];          /* SHA256 校验和（可选）*/
    char release_notes[1024];           /* 更新说明 */
    bool mandatory;                     /* 是否强制更新 */
    char request_id[64];               /* 请求ID（用于进度跟踪）*/
} update_info_t;

/* 下载进度结构 */
typedef struct {
    char request_id[64];               /* 关联的请求ID */
    int progress;                      /* 进度 0-100 */
    int64_t downloaded;                 /* 已下载字节数 */
    int64_t total_size;                 /* 总文件大小 */
    double speed;                       /* 下载速度 (bytes/s) */
    char error[512];                   /* 错误信息 */
} download_progress_t;

/* 进度回调函数类型 */
typedef void (*progress_callback_t)(
    const char *url,
    int progress,
    int64_t downloaded,
    int64_t total_size,
    void *user_data
);

/* HTTP 下载配置 */
typedef struct {
    char url[512];
    char output_path[512];
    char temp_path[512];
    int timeout;                        /* 超时（秒）*/
    int max_speed;                      /* 最大速度限制 (bytes/s) */
    bool enable_resume;                 /* 是否启用断点续传 */
    bool verify_ssl;                    /* 是否验证SSL */
    char ca_cert_path[256];              /* CA证书路径 */
    progress_callback_t callback;       /* 进度回调函数 */
    void *user_data;                    /* 用户数据指针 */
} http_download_config_t;

/* TCP 下载配置 */
typedef struct {
    char file_path[512];
    char output_path[512];
    int64_t offset;                   /* 断点续传位置 */
    int64_t total_size;               /* 文件总大小 */
    int chunk_size;                   /* 传输块大小 */
    int timeout;                      /* 超时设置（秒）*/
    int max_retries;                  /* 最大重试次数 */
    progress_callback_t callback;     /* 进度回调函数 */
    void *user_data;                  /* 用户数据指针 */
} tcp_download_config_t;

/* Agent配置结构 */
typedef struct {
    char server_addr[256];      /* Socket服务器地址 (host:port) */
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
    bool use_ssl;              /* 是否使用SSL */
    char ca_path[256];         /* CA证书路径 */
    
    /* 更新配置 */
    bool enable_auto_update;            /* 是否启用自动更新 */
    int update_check_interval;          /* 检查更新间隔（秒）*/
    char update_channel[32];            /* 更新渠道：stable/beta/dev */
    bool update_require_confirm;         /* 更新前是否需要确认 */
    char update_temp_path[256];          /* 临时文件路径 */
    char update_backup_path[256];       /* 备份路径 */
    bool update_rollback_on_fail;       /* 失败是否自动回滚 */
    int update_rollback_timeout;         /* 回滚超时（秒）*/
    bool update_verify_checksum;         /* 是否校验文件校验和 */
    char update_ca_cert_path[256];       /* 更新CA证书路径 */
} agent_config_t;

/* PTY会话结构 */
typedef struct {
    int session_id;             /* 会话ID */
    int master_fd;              /* PTY master fd */
    pid_t child_pid;           /* 子进程PID */
    pthread_t read_thread;      /* 读取线程 */
    bool active;               /* 是否活跃 */
    int rows;                  /* 终端行数 */
    int cols;                  /* 终端列数 */
    time_t last_activity;       /* 最后活动时间戳 */
} pty_session_t;

/* Agent上下文结构 */
typedef struct {
    agent_config_t config;      /* 配置 */
    void *socket_client;        /* Socket客户端 */
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

/* agent_socket.c */
int socket_connect(agent_context_t *ctx);
void socket_disconnect(agent_context_t *ctx);
int socket_send_message(agent_context_t *ctx, msg_type_t type, const char *data, size_t len);
int socket_send_json(agent_context_t *ctx, msg_type_t type, const char *json);
void socket_cleanup(void);
void socket_enable_reconnect(agent_context_t *ctx);
void socket_disable_reconnect(agent_context_t *ctx);

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
int log_read_file(agent_context_t *ctx, const char *filepath, int offset, int length);

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
void *pty_timeout_thread(void *arg);

/* agent_protocol.c */
int protocol_handle_message(agent_context_t *ctx, const char *data, size_t len);
char *protocol_create_auth_msg(agent_context_t *ctx);
char *protocol_create_heartbeat(agent_context_t *ctx);

/* agent_http.c */
int http_init(void);
void http_cleanup(void);
char *http_get_string(const char *url, int timeout);
char *http_post_json(const char *url, const char *json, int timeout);
int http_download_file(const char *url, const char *output_path, http_download_config_t *config);
int http_can_resume(const char *url, const char *output_path);
int http_calc_md5(const char *filepath, char *md5_str);
int http_calc_sha256(const char *filepath, char *sha256_str);
bool http_verify_checksum(const char *filepath, const char *expected_md5, const char *expected_sha256);

/* agent_tcp_download.c */
int tcp_download_init(void);
void tcp_download_cleanup(void);
int tcp_download_file(agent_context_t *ctx, const char *file_path, const char *output_path, tcp_download_config_t *config);
int tcp_can_resume(const char *file_path, const char *output_path);
int tcp_calc_md5(const char *filepath, char *md5_str);
int tcp_calc_sha256(const char *filepath, char *sha256_str);
bool tcp_verify_checksum(const char *filepath, const char *expected_md5, const char *expected_sha256);
int tcp_handle_download_response(agent_context_t *ctx, const char *data, size_t len);

/* agent_update.c */
int update_check_version(agent_context_t *ctx);
int update_request_update(agent_context_t *ctx);
int update_download_package(const char *url, const char *output_path, progress_callback_t callback, void *user_data);
int update_verify_package(const char *filepath, const char *expected_md5, const char *expected_sha256);
int update_backup_current_version(const char *backup_dir, char *backup_path);
int update_install_package(const char *package_path);
void update_restart_agent(void);
int update_rollback_to_backup(const char *backup_path);
int update_report_status(agent_context_t *ctx, update_status_t status, const char *message, int progress);
void download_progress_callback(const char *url, int progress, int64_t downloaded, int64_t total_size, void *user_data);

/* JSON 解析函数 */
char *json_get_string(const char *json, const char *key);
int json_get_int(const char *json, const char *key, int default_val);
int64_t json_get_int64(const char *json, const char *key);
bool json_get_bool(const char *json, const char *key, bool default_val);

/* agent_util.c */
void agent_log(int level, const char *fmt, ...);
void set_log_level(int level);
int set_log_file(const char *path);
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
int copy_file(const char *src_path, const char *dst_path);

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
