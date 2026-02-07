/*
 * 脚本下发执行模块
 * 支持保存、执行脚本，并回传执行结果
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <errno.h>
#include <dirent.h>
#include <time.h>
#include <signal.h>
#include <pthread.h>
#include "agent.h"

#define SCRIPT_OUTPUT_MAX   (64 * 1024)  /* 最大输出64KB */
#define SCRIPT_TIMEOUT_SEC  300           /* 脚本超时时间 */

/* 脚本执行任务结构 */
typedef struct {
    agent_context_t *ctx;
    char script_id[64];
    char script_path[256];
    char content[8192];
    bool inline_script;
} script_task_t;

/* 确保脚本目录存在 */
static int ensure_script_dir(const char *path)
{
    struct stat st;
    if (stat(path, &st) == 0) {
        return S_ISDIR(st.st_mode) ? 0 : -1;
    }
    
    /* 递归创建目录 */
    char tmp[256];
    snprintf(tmp, sizeof(tmp), "%s", path);

    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            mkdir(tmp, 0755);
            *p = '/';
        }
    }
    
    return mkdir(tmp, 0755);
}

/* 保存脚本到文件 */
int script_save(const char *script_id, const char *content, const char *path)
{
    if (!script_id || !content || !path) return -1;
    
    /* 确保目录存在 */
    char dir[256];
    snprintf(dir, sizeof(dir), "%s", path);
    char *last_slash = strrchr(dir, '/');
    if (last_slash) {
        *last_slash = '\0';
        ensure_script_dir(dir);
    }
    
    FILE *fp = fopen(path, "w");
    if (!fp) {
        LOG_ERROR("无法创建脚本文件: %s (错误: %s)", path, strerror(errno));
        return -1;
    }
    
    /* 写入脚本内容 */
    size_t len = strlen(content);
    if (fwrite(content, 1, len, fp) != len) {
        LOG_ERROR("写入脚本失败: %s", path);
        fclose(fp);
        return -1;
    }
    
    fclose(fp);
    
    /* 设置可执行权限 */
    chmod(path, 0755);
    
    LOG_INFO("脚本已保存: %s (ID: %s, 大小: %zu bytes)", path, script_id, len);
    return 0;
}

/* 执行脚本并捕获输出 */
static int execute_script_internal(const char *script_path, char **output, int *exit_code)
{
    int pipefd[2];
    if (pipe(pipefd) == -1) {
        LOG_ERROR("创建管道失败");
        return -1;
    }
    
    pid_t pid = fork();
    if (pid == -1) {
        LOG_ERROR("fork失败");
        close(pipefd[0]);
        close(pipefd[1]);
        return -1;
    }
    
    if (pid == 0) {
        /* 子进程 */
        close(pipefd[0]);  /* 关闭读端 */
        
        /* 重定向stdout和stderr到管道 */
        dup2(pipefd[1], STDOUT_FILENO);
        dup2(pipefd[1], STDERR_FILENO);
        close(pipefd[1]);
        
        /* 设置环境变量 */
        setenv("PATH", "/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin", 1);
        
        /* 执行脚本 */
        execl("/bin/sh", "sh", "-c", script_path, NULL);
        
        /* exec失败 */
        fprintf(stderr, "执行失败: %s\n", strerror(errno));
        _exit(127);
    }
    
    /* 父进程 */
    close(pipefd[1]);  /* 关闭写端 */
    
    /* 读取输出 */
    *output = malloc(SCRIPT_OUTPUT_MAX);
    if (!*output) {
        close(pipefd[0]);
        waitpid(pid, NULL, 0);
        return -1;
    }
    
    size_t total_read = 0;
    ssize_t n;
    
    /* 设置非阻塞 */
    int flags = fcntl(pipefd[0], F_GETFL, 0);
    fcntl(pipefd[0], F_SETFL, flags | O_NONBLOCK);
    
    time_t start_time = time(NULL);
    
    while (1) {
        n = read(pipefd[0], *output + total_read, SCRIPT_OUTPUT_MAX - total_read - 1);
        
        if (n > 0) {
            total_read += n;
        } else if (n == 0) {
            break;  /* EOF */
        } else if (errno == EAGAIN || errno == EWOULDBLOCK) {
            /* 检查超时 */
            if (time(NULL) - start_time > SCRIPT_TIMEOUT_SEC) {
                LOG_WARN("脚本执行超时，终止进程");
                kill(pid, SIGKILL);
                break;
            }
            usleep(10000);  /* 10ms */
        } else {
            break;  /* 错误 */
        }
        
        if (total_read >= SCRIPT_OUTPUT_MAX - 1) {
            LOG_WARN("脚本输出过长，截断");
            break;
        }
    }
    
    (*output)[total_read] = '\0';
    close(pipefd[0]);
    
    /* 等待子进程结束 */
    int status;
    waitpid(pid, &status, 0);
    
    if (WIFEXITED(status)) {
        *exit_code = WEXITSTATUS(status);
    } else if (WIFSIGNALED(status)) {
        *exit_code = 128 + WTERMSIG(status);
    } else {
        *exit_code = -1;
    }
    
    return 0;
}

/* 发送执行结果 */
static void send_script_result(agent_context_t *ctx, const char *script_id,
                               int exit_code, const char *output)
{
    if (!ctx || !script_id) return;
    
    size_t output_len = output ? strlen(output) : 0;
    size_t json_size = output_len * 2 + 512;  /* 预留转义空间 */
    
    char *json = malloc(json_size);
    if (!json) return;
    
    /* 转义输出中的特殊字符 */
    char *escaped_output = malloc(output_len * 2 + 1);
    if (!escaped_output) {
        free(json);
        return;
    }
    
    size_t j = 0;
    for (size_t i = 0; i < output_len && j < output_len * 2 - 1; i++) {
        char c = output[i];
        switch (c) {
            case '"':  escaped_output[j++] = '\\'; escaped_output[j++] = '"'; break;
            case '\\': escaped_output[j++] = '\\'; escaped_output[j++] = '\\'; break;
            case '\n': escaped_output[j++] = '\\'; escaped_output[j++] = 'n'; break;
            case '\r': escaped_output[j++] = '\\'; escaped_output[j++] = 'r'; break;
            case '\t': escaped_output[j++] = '\\'; escaped_output[j++] = 't'; break;
            default:
                if (c >= 0x20 && c < 0x7f) {
                    escaped_output[j++] = c;
                } else {
                    /* 跳过控制字符 */
                }
                break;
        }
    }
    escaped_output[j] = '\0';
    
    snprintf(json, json_size,
        "{"
        "\"script_id\":\"%s\","
        "\"exit_code\":%d,"
        "\"success\":%s,"
        "\"output\":\"%s\","
        "\"timestamp\":%llu"
        "}",
        script_id,
        exit_code,
        exit_code == 0 ? "true" : "false",
        escaped_output,
        get_timestamp_ms());
    
    ws_send_json(ctx, MSG_TYPE_SCRIPT_RESULT, json);
    
    free(escaped_output);
    free(json);
}

/* 脚本执行线程 */
static void *script_execute_thread(void *arg)
{
    script_task_t *task = (script_task_t *)arg;
    
    char *output = NULL;
    int exit_code = -1;
    char exec_cmd[512];
    
    if (task->inline_script) {
        /* 内联脚本，先保存到临时文件 */
        char tmp_path[256];
        snprintf(tmp_path, sizeof(tmp_path), "/tmp/agent_script_%s.sh", task->script_id);
        
        if (script_save(task->script_id, task->content, tmp_path) != 0) {
            send_script_result(task->ctx, task->script_id, -1, "保存脚本失败");
            free(task);
            return NULL;
        }
        
        snprintf(exec_cmd, sizeof(exec_cmd), "/bin/sh %s", tmp_path);
    } else {
        snprintf(exec_cmd, sizeof(exec_cmd), "/bin/sh %s", task->script_path);
    }
    
    LOG_INFO("执行脚本: %s (ID: %s)", exec_cmd, task->script_id);
    
    if (execute_script_internal(exec_cmd, &output, &exit_code) == 0) {
        LOG_INFO("脚本执行完成: ID=%s, exit_code=%d", task->script_id, exit_code);
        send_script_result(task->ctx, task->script_id, exit_code, output);
    } else {
        LOG_ERROR("脚本执行失败: %s", task->script_id);
        send_script_result(task->ctx, task->script_id, -1, "执行失败");
    }
    
    if (output) free(output);
    
    /* 清理临时文件 */
    if (task->inline_script) {
        char tmp_path[256];
        snprintf(tmp_path, sizeof(tmp_path), "/tmp/agent_script_%s.sh", task->script_id);
        unlink(tmp_path);
    }
    
    free(task);
    return NULL;
}

/* 执行已保存的脚本 */
int script_execute(agent_context_t *ctx, const char *script_id, const char *script_path)
{
    if (!ctx || !script_id || !script_path) return -1;
    
    if (!ctx->config.enable_script) {
        LOG_WARN("脚本执行已禁用");
        send_script_result(ctx, script_id, -1, "脚本执行已禁用");
        return -1;
    }
    
    /* 检查脚本文件是否存在 */
    if (access(script_path, X_OK) != 0) {
        LOG_ERROR("脚本文件不存在或不可执行: %s", script_path);
        send_script_result(ctx, script_id, -1, "脚本文件不存在或不可执行");
        return -1;
    }
    
    /* 创建执行任务 */
    script_task_t *task = calloc(1, sizeof(script_task_t));
    if (!task) return -1;
    
    task->ctx = ctx;
    snprintf(task->script_id, sizeof(task->script_id), "%s", script_id);
    snprintf(task->script_path, sizeof(task->script_path), "%s", script_path);
    task->inline_script = false;
    
    /* 创建执行线程 */
    pthread_t thread;
    if (pthread_create(&thread, NULL, script_execute_thread, task) != 0) {
        free(task);
        return -1;
    }
    
    pthread_detach(thread);
    return 0;
}

/* 执行内联脚本 */
int script_execute_inline(agent_context_t *ctx, const char *script_id, const char *content)
{
    if (!ctx || !script_id || !content) return -1;
    
    if (!ctx->config.enable_script) {
        LOG_WARN("脚本执行已禁用");
        send_script_result(ctx, script_id, -1, "脚本执行已禁用");
        return -1;
    }
    
    /* 创建执行任务 */
    script_task_t *task = calloc(1, sizeof(script_task_t));
    if (!task) return -1;
    
    task->ctx = ctx;
    snprintf(task->script_id, sizeof(task->script_id), "%s", script_id);
    snprintf(task->content, sizeof(task->content), "%s", content);
    task->inline_script = true;
    
    /* 创建执行线程 */
    pthread_t thread;
    if (pthread_create(&thread, NULL, script_execute_thread, task) != 0) {
        free(task);
        return -1;
    }
    
    pthread_detach(thread);
    return 0;
}

/* 列出已保存的脚本 */
int script_list(agent_context_t *ctx)
{
    if (!ctx) return -1;
    
    const char *script_dir = ctx->config.script_path;
    if (!script_dir || script_dir[0] == '\0') {
        script_dir = DEFAULT_SCRIPT_PATH;
    }
    
    DIR *dir = opendir(script_dir);
    if (!dir) {
        LOG_WARN("脚本目录不存在: %s", script_dir);
        return -1;
    }
    
    char json[4096];
    int offset = snprintf(json, sizeof(json), "{\"scripts\":[");
    
    struct dirent *entry;
    int count = 0;
    
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_type != DT_REG) continue;
        
        char filepath[512];
        snprintf(filepath, sizeof(filepath), "%s/%s", script_dir, entry->d_name);
        
        struct stat st;
        if (stat(filepath, &st) == 0) {
            offset += snprintf(json + offset, sizeof(json) - offset,
                "%s{\"name\":\"%s\",\"size\":%ld,\"mtime\":%ld}",
                count > 0 ? "," : "", entry->d_name, (long)st.st_size, (long)st.st_mtime);
            count++;
        }
    }
    
    closedir(dir);
    
    snprintf(json + offset, sizeof(json) - offset, "]}");
    ws_send_json(ctx, MSG_TYPE_FILE_DATA, json);
    
    return 0;
}

/* 删除脚本 */
int script_delete(agent_context_t *ctx, const char *script_name)
{
    if (!ctx || !script_name) return -1;
    
    const char *script_dir = ctx->config.script_path;
    if (!script_dir || script_dir[0] == '\0') {
        script_dir = DEFAULT_SCRIPT_PATH;
    }
    
    char filepath[512];
    snprintf(filepath, sizeof(filepath), "%s/%s", script_dir, script_name);
    
    /* 安全检查：防止路径遍历 */
    if (strstr(script_name, "..") != NULL || script_name[0] == '/') {
        LOG_ERROR("非法脚本名称: %s", script_name);
        return -1;
    }
    
    if (unlink(filepath) == 0) {
        LOG_INFO("删除脚本: %s", filepath);
        return 0;
    } else {
        LOG_ERROR("删除脚本失败: %s (%s)", filepath, strerror(errno));
        return -1;
    }
}
