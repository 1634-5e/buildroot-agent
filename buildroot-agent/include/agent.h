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

/* 版本信息 (由构建系统从 VERSION 文件传入) */
#define AGENT_NAME          "buildroot-agent"

/* 默认配置 */
#define DEFAULT_SERVER_ADDR     "127.0.0.1:8766"
#define DEFAULT_HEARTBEAT_SEC   30
#define DEFAULT_RECONNECT_SEC   5
#define DEFAULT_LOG_PATH        "./log"
#define DEFAULT_SCRIPT_PATH     "./scripts"
#define DEFAULT_CONFIG_PATH     "./agent.cfg"

/* 配置加载结果 */
typedef enum {
    CONFIG_LOAD_OK = 0,
    CONFIG_LOAD_NOT_FOUND,
    CONFIG_LOAD_PARSE_ERROR,
} config_load_result_t;

/* 配置覆盖项 (用于命令行参数和环境变量) */
typedef struct {
    const char *server_addr;
    const char *device_id;
    const char *log_path;
    const char *script_path;
    int log_level;
    bool log_level_set;
    bool use_ssl;
    bool use_ssl_set;
    const char *ca_path;
} config_override_t;

/* 消息协议 */
#define MESSAGE_HEADER_SIZE 3     /* msg_type(1) + length(2) */
#define MAX_MESSAGE_SIZE 65535     /* 最大消息大小 */

/* 更新相关默认配置 */
#define DEFAULT_UPDATE_CHECK_INTERVAL   1800       /* 30分钟 */
#define DEFAULT_UPDATE_CHANNEL          "stable"
#define DEFAULT_UPDATE_TEMP_PATH       "./tmp"
#define DEFAULT_UPDATE_BACKUP_PATH     "./backup"
#define DEFAULT_UPDATE_ROLLBACK_TIMEOUT 300        /* 5分钟 */
#define DEFAULT_DOWNLOAD_TIMEOUT       1800       /* 30分钟 */
#define DEFAULT_MAX_DOWNLOAD_SPEED    1048576    /* 1MB/s */

/* 消息类型定义 */
typedef enum {
    MSG_TYPE_REGISTER     = 0xF0,     /* 设备注册 */
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
    MSG_TYPE_CMD_REQUEST    = 0x30,     /* 命令请求 */
    MSG_TYPE_CMD_RESPONSE   = 0x31,     /* 命令响应 */
MSG_TYPE_DEVICE_LIST    = 0x50,     /* 设备列表更新 */
    MSG_TYPE_DEVICE_DISCONNECT = 0x51,  /* 设备断开通知 */
    MSG_TYPE_DEVICE_UPDATE  = 0x52,     /* 设备更新通知 */
    MSG_TYPE_REGISTER_RESULT = 0xF1,    /* 注册结果 */

    /* 更新管理消息 */
    MSG_TYPE_UPDATE_CHECK         = 0x60,   /* 检查更新请求 */
    MSG_TYPE_UPDATE_INFO          = 0x61,   /* 更新信息响应 */
    MSG_TYPE_UPDATE_DOWNLOAD      = 0x62,   /* 请求批准下载更新包 */
    MSG_TYPE_UPDATE_PROGRESS      = 0x63,   /* 上报下载进度 */
    MSG_TYPE_UPDATE_COMPLETE      = 0x65,   /* 更新完成 */
    MSG_TYPE_UPDATE_ERROR         = 0x66,   /* 更新错误 */
    MSG_TYPE_UPDATE_ROLLBACK      = 0x67,   /* 更新回滚 */
    MSG_TYPE_UPDATE_REQUEST_APPROVAL = 0x68,   /* 请求Web批准下载 */
    MSG_TYPE_UPDATE_DOWNLOAD_READY = 0x69,   /* 下载完成，请求批准安装 */
    MSG_TYPE_UPDATE_APPROVE_INSTALL = 0x6A,   /* Web批准安装 */
    MSG_TYPE_UPDATE_DENY          = 0x6B,   /* Web拒绝请求 */
    MSG_TYPE_UPDATE_APPROVE_DOWNLOAD = 0x6C,   /* Web批准下载（服务器转发）*/
    /* Ping监控消息 */
    MSG_TYPE_PING_STATUS = 0x70,       /* Ping状态上报 */
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
    UPDATE_STATUS_IDLE = 0,
    UPDATE_STATUS_CHECKING = 1,
    UPDATE_STATUS_DOWNLOADING = 2,
    UPDATE_STATUS_VERIFYING = 3,
    UPDATE_STATUS_BACKING_UP = 4,
    UPDATE_STATUS_INSTALLING = 5,
    UPDATE_STATUS_RESTARTING = 6,
    UPDATE_STATUS_COMPLETE = 7,
    UPDATE_STATUS_FAILED = 8,
    UPDATE_STATUS_ROLLING_BACK = 9,
    UPDATE_STATUS_ROLLBACK_COMPLETE = 10,
    
    /* 新增状态（用于双批准流程） */
    UPDATE_STATUS_CHECKED = 100,        /* 已检查到新版本，等待批准 */
    UPDATE_STATUS_APPROVAL_SENT = 101,  /* 已发送批准请求，等待响应 */
    UPDATE_STATUS_APPROVED_DOWNLOAD = 102, /* 已批准下载，准备下载 */
    UPDATE_STATUS_DOWNLOADED = 103,     /* 下载完成，等待安装批准 */
    UPDATE_STATUS_INSTALL_SENT = 104,    /* 已发送安装批准请求，等待响应 */
    UPDATE_STATUS_APPROVED_INSTALL = 105,  /* 已批准安装，准备安装 */
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

/* 下载完成回调函数类型 */
typedef void (*completion_callback_t)(
    const char *url,
    const char *output_path,
    int64_t file_size,
    bool success,
    const char *error_msg,
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
    completion_callback_t completion; /* 完成回调函数 */
} tcp_download_config_t;

/* Ping结果状态 */
typedef enum {
    PING_STATUS_UNKNOWN = 0,      /* 未知状态 */
    PING_STATUS_REACHABLE = 1,     /* 可达 */
    PING_STATUS_UNREACHABLE = 2,   /* 不可达 */
    PING_STATUS_TIMEOUT = 3         /* 超时 */
} ping_result_status_t;

/* Ping目标配置 */
typedef struct {
    char ip[64];                /* 目标IP地址 */
    char name[64];               /* 目标名称（可选） */
    int interval;                /* Ping间隔（秒） */
    int timeout;                /* Ping超时（秒） */
    int count;                  /* 每次ping的包数量 */
} ping_target_t;

/* Ping结果数据 */
typedef struct {
    char ip[64];                /* 目标IP地址 */
    int status;                 /* 状态：0=未知, 1=可达, 2=不可达, 3=超时 */
    float avg_time;              /* 平均延迟（毫秒） */
    float min_time;              /* 最小延迟（毫秒） */
    float max_time;              /* 最大延迟（毫秒） */
    float packet_loss;            /* 丢包率（百分比） */
    int packets_sent;            /* 发送包数 */
    int packets_received;        /* 接收包数 */
    uint64_t timestamp;          /* 时间戳（毫秒） */
} ping_result_t;

/* Ping状态消息 */
typedef struct {
    ping_result_t results[16];    /* Ping结果数组（最多16个目标） */
    int result_count;             /* 结果数量 */
    uint64_t timestamp;          /* 上报时间戳（毫秒） */
} ping_status_t;



/* Agent配置结构 */
typedef struct {
    char server_addr[256];      /* Socket服务器地址 (host:port) */
    char device_id[64];         /* 设备ID */
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
    bool enable_auto_update;            /* 是否启用自动更新 */
    int update_check_interval;          /* 检查更新间隔（秒）*/
    char update_channel[32];            /* 更新渠道：stable/beta/dev */
    bool update_require_confirm;        /* 更新前是否需要确认 */
    char update_temp_path[256];         /* 临时文件路径 */
    char update_backup_path[256];       /* 备份路径 */
    bool update_rollback_on_fail;       /* 失败是否自动回滚 */
    int update_rollback_timeout;        /* 回滚超时（秒）*/
    bool update_verify_checksum;        /* 是否校验文件校验和 */
    /* Ping监控配置 */
    bool enable_ping;                    /* 是否启用ping监控 */
    int ping_interval;                  /* Ping上报间隔（秒）*/
    ping_target_t ping_targets[16];       /* Ping目标列表（最多16个） */
    int ping_target_count;               /* Ping目标数量 */
    int ping_timeout;                   /* Ping超时（秒，默认5）*/
    int ping_count;                    /* 每次ping的包数量（默认4）*/
    
    /* Device Twin (MQTT) 配置 */
    bool enable_twin;                    /* 是否启用Device Twin */
    char mqtt_broker[256];              /* MQTT Broker地址 */
    int mqtt_port;                      /* MQTT端口 */
    char mqtt_username[128];            /* MQTT用户名 */
    char mqtt_password[128];            /* MQTT密码 */
    int twin_report_interval;           /* Twin上报间隔（秒）*/
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
    bool registered;            /* 注册状态 */
    bool running;               /* 运行状态 */
    pthread_mutex_t lock;       /* 互斥锁 */
    pty_session_t *pty_sessions;/* PTY会话数组 */
    int pty_session_count;      /* PTY会话数量 */
    int max_pty_sessions;       /* 最大PTY会话数 */
    
    /* Device Twin */
    void *twin_sync;            /* twin_sync_t 指针 (避免头文件依赖) */
    void *twin_state;           /* twin_state_t 指针 */
} agent_context_t;

/* 全局Agent上下文 */
extern agent_context_t *g_agent_ctx;

/* 批准请求超时（3分钟） */
#define UPDATE_APPROVAL_TIMEOUT 180

/* 更新相关全局变量 */
extern update_status_t g_update_status;
extern pthread_mutex_t g_update_lock;
extern update_info_t g_update_info;
/* 更新模式标志，防止信号处理导致提前退出 */
extern bool g_in_update;

/* 批准请求相关 */
extern bool g_approval_sent;
extern char g_current_request_id[64];
extern char g_downloaded_file_path[512];

/* 平台兼容性定义 */
#ifndef PRIu64
#define PRIu64 "lu"
#endif

/* 函数声明 */

/* agent_main.c */
int agent_init(const char *config_path, const config_override_t *overrides);
int agent_start(void);
void agent_stop(void);
void agent_cleanup(void);

/* agent_config.c */
config_load_result_t config_load(agent_config_t *config, const char *path);
config_load_result_t config_load_yaml(agent_config_t *config, const char *path);
int config_save(agent_config_t *config, const char *path);
void config_set_defaults(agent_config_t *config);
void config_apply_overrides(agent_config_t *config, const config_override_t *overrides);
void config_load_from_env(agent_config_t *config);
int config_validate(agent_config_t *config);
void config_print(agent_config_t *config);
int config_save_example(agent_config_t *config, const char *path);

/* agent_socket.c */
int socket_connect(agent_context_t *ctx);
void socket_disconnect(agent_context_t *ctx);
int socket_send_message(agent_context_t *ctx, msg_type_t type, const char *data, size_t len);
int socket_send_json(agent_context_t *ctx, msg_type_t type, const char *json);
void socket_cleanup(void);
void socket_enable_reconnect(agent_context_t *ctx);
void socket_disable_reconnect(agent_context_t *ctx);
void socket_registration_complete(agent_context_t *ctx, bool success);

/* agent_status.c */
int status_collect(system_status_t *status);
char *status_to_json(const system_status_t *status);
void *status_thread(void *arg);

/* agent_log.c */
int log_upload_file(agent_context_t *ctx, const char *filepath, const char *request_id);
int log_tail_file(agent_context_t *ctx, const char *filepath, int lines, const char *request_id);
int log_watch_start(agent_context_t *ctx, const char *filepath, const char *request_id);
void log_watch_stop(agent_context_t *ctx, const char *filepath);
void log_watch_stop_all(void);
int log_list_files(agent_context_t *ctx, const char *filepath, const char *request_id);
int log_read_file(agent_context_t *ctx, const char *filepath, int offset, int length, const char *request_id);
int log_write_file(agent_context_t *ctx, const char *filepath, const char *content_b64, int64_t mtime, int force, const char *request_id);

/* agent_script.c */
int script_save(const char *script_id, const char *content, const char *path);
int script_execute(agent_context_t *ctx, const char *script_id, const char *script_path);
int script_execute_inline(agent_context_t *ctx, const char *script_id, const char *content);
int script_list(agent_context_t *ctx);

/* agent_ping.c */
int ping_execute(const char *ip, int timeout, int count, ping_result_t *result);
int ping_execute_all(agent_context_t *ctx);
char *ping_status_to_json(ping_status_t *status);
void *ping_thread(void *arg);
int ping_init_from_config(const agent_config_t *config);
int ping_save_config(agent_config_t *config, const char *path);

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
char *protocol_create_heartbeat(const agent_context_t *ctx);

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

/* 新增：批准请求相关 */
int update_send_approval_request(agent_context_t *ctx, update_info_t *info);
int update_send_download_ready(agent_context_t *ctx, const char *version, 
                               const char *file_path, int64_t file_size,
                               const char *md5_checksum);
int update_handle_approve_install(agent_context_t *ctx, const char *data);
int update_handle_deny(agent_context_t *ctx, const char *data);

/* 新增：超时检测相关 */
void start_timeout_checker(agent_context_t *ctx);
void stop_timeout_checker(void);

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
char *get_exe_path(void);
char *get_exe_dir(void);
uint64_t get_timestamp_ms(void);
int mkdir_recursive(const char *path, mode_t mode);
bool file_exists(const char *path);
long get_file_size(const char *path);
void safe_strncpy(char *dest, const char *src, size_t size);
char *str_trim(char *str);
int daemonize(void);
int write_pid_file(const char *path);
int write_file_content(const char *path, const char *content, size_t size);
size_t base64_decode(const char *input, unsigned char *output);
void remove_pid_file(const char *path);
bool is_process_running(const char *pid_file);
int copy_file(const char *src_path, const char *dst_path);

/* agent_twin.c - Device Twin 集成 */
int agent_twin_init(agent_context_t *ctx);
int agent_twin_start(agent_context_t *ctx);
void agent_twin_stop(agent_context_t *ctx);
void agent_twin_cleanup(agent_context_t *ctx);
int agent_twin_report_status(agent_context_t *ctx, const system_status_t *status);

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
