# PITFALLS.md - 常见错误对照表

> **快速查找：** 遇到问题时，先在这里找答案。

---

## CMake 相关

### cmake -B 参数不支持

```bash
# ✗ 错误
cmake -B build
# 错误信息：unknown argument '-B'

# ✓ 正确
mkdir -p build && cd build && cmake ..
```

**原因：** cmake 2.8.12 版本太老，不支持 `-B` 参数。

**版本要求：** cmake ≥ 3.13 才支持 `-B` 参数。

---

### 静态链接失败

```bash
# 错误信息
/usr/bin/ld: cannot find -lc

# 解决方案
apt-get install libc6-dev
# 或
yum install glibc-static
```

---

## 内存管理

### 未检查 malloc 返回值

```c
// ✗ 错误 - 嵌入式环境可能分配失败
char *buf = malloc(size);
memcpy(buf, src, size);  // 可能崩溃！

// ✓ 正确
char *buf = malloc(size);
if (buf == NULL) {
    LOG_ERROR("malloc failed: %s", strerror(errno));
    return -1;
}
memcpy(buf, src, size);
```

---

### 重复释放 (double free)

```c
// ✗ 错误
free(ptr);
// ... 其他代码 ...
free(ptr);  // 崩溃！

// ✓ 正确
free(ptr);
ptr = NULL;  // 防止重复释放

// 或使用 guard 模式
static void safe_free(void **ptr) {
    if (ptr && *ptr) {
        free(*ptr);
        *ptr = NULL;
    }
}
```

---

### 内存泄漏

```c
// ✗ 错误 - 提前返回未释放
int process(const char *path) {
    char *buf = malloc(1024);
    
    if (some_error) {
        return -1;  // 泄漏！
    }
    
    free(buf);
    return 0;
}

// ✓ 正确 - 使用 goto error 模式
int process(const char *path) {
    char *buf = NULL;
    int result = -1;
    
    buf = malloc(1024);
    if (!buf) {
        LOG_ERROR("malloc failed");
        goto error;
    }
    
    if (some_error) {
        LOG_ERROR("process failed");
        goto error;
    }
    
    result = 0;
    
error:
    if (buf) free(buf);
    return result;
}
```

---

## 字符串操作

### strcpy 缓冲区溢出

```c
// ✗ 错误 - 可能溢出
char dest[64];
strcpy(dest, src);  // src 可能超过 64 字节

// ✓ 正确
char dest[64];
safe_strncpy(dest, src, sizeof(dest));

// 或
snprintf(dest, sizeof(dest), "%s", src);
```

---

### sprintf 缓冲区溢出

```c
// ✗ 错误
char buf[64];
sprintf(buf, "value: %d", value);  // 可能溢出

// ✓ 正确
char buf[64];
snprintf(buf, sizeof(buf), "value: %d", value);
```

---

## 文件操作

### 追加模式 fseek 无效

```c
// ✗ 错误 - 追加模式 fseek 无效
FILE *fp = fopen(path, "ab");
fseek(fp, offset, SEEK_SET);  // 被忽略！
fwrite(data, 1, len, fp);

// ✓ 正确 - 使用 r+b 模式
FILE *fp = fopen(path, "r+b");
fseek(fp, offset, SEEK_SET);
fwrite(data, 1, len, fp);
```

**原因：** C 标准规定，追加模式 (`"a"`) 下，所有写入都在文件末尾，`fseek` 被忽略。

---

### 文件打开未检查

```c
// ✗ 错误
FILE *fp = fopen(path, "r");
fgets(buf, sizeof(buf), fp);  // fp 可能为 NULL

// ✓ 正确
FILE *fp = fopen(path, "r");
if (!fp) {
    LOG_ERROR("fopen failed: %s", strerror(errno));
    return -1;
}
```

---

## 协议相关

### 系统状态响应类型错误

```c
// ✗ 错误 - Web 无法路由响应
void handle_status_query(agent_context_t *ctx, const char *request_id) {
    char *json = build_system_status_json();
    send_message(ctx, MSG_TYPE_SYSTEM_STATUS, json);  // 无 request_id！
}

// ✓ 正确 - 使用 CMD_RESPONSE
void handle_status_query(agent_context_t *ctx, const char *request_id) {
    char *json = build_system_status_json();
    char *response = add_request_id(json, request_id);
    send_message(ctx, MSG_TYPE_CMD_RESPONSE, response);
}
```

**原因：** 
- `SYSTEM_STATUS (0x02)` 是主动上报，无 `request_id`
- `CMD_RESPONSE (0x31)` 是查询响应，必须有 `request_id`
- Server 通过 `request_id` 将响应路由给正确的 Web 客户端

---

### 消息类型不同步

```c
// 如果在 agent.h 添加了新类型
typedef enum {
    MSG_TYPE_NEW_FEATURE = 0x80,  // 新增
} msg_type_t;

// 必须同步在 constants.py 添加
class MessageType(IntEnum):
    NEW_FEATURE = 0x80  # 必须同步！

// 必须同步在 PROTOCOL.md 添加
| NEW_FEATURE | 0x80 | 新功能 | ... |
```

**不同步的后果：**
- Agent 发送 `0x80`
- Server 无法识别（如果 Python 未同步）
- 消息被丢弃或解析错误

---

### 字段命名不一致

```json
// ✗ 错误 - 混用命名风格
{
    "sessionId": 1,      // 驼峰
    "device_id": "dev1"  // 下划线
}

// ✓ 正确 - 统一使用 snake_case
{
    "session_id": 1,
    "device_id": "dev1"
}
```

**注意：** C 代码已兼容两种命名，但新代码应使用 `snake_case`。

---

## Python 相关

### except: pass 吞掉异常

```python
# ✗ 禁止 - 吞掉所有异常
try:
    do_something()
except:
    pass

# ✓ 正确 - 明确异常类型
try:
    do_something()
except ValueError as e:
    logger.error(f"值错误: {e}")
except Exception as e:
    logger.error(f"未知错误: {e}", exc_info=True)
    raise
```

---

### 未使用的导入

```python
# ✗ 错误 - ruff F401
import os  # 未使用
from typing import Optional  # 未使用

def hello():
    print("hello")

# ✓ 正确 - 只导入需要的
def hello():
    print("hello")
```

**检查命令：** `uv run ruff check .`

---

### 未使用的变量

```python
# ✗ 错误 - ruff F841
def process():
    result = calculate()  # 未使用
    return "done"

# ✓ 正确
def process():
    calculate()  # 不赋值
    return "done"

# 或
def process():
    result = calculate()
    return result
```

---

## JavaScript 相关

### 使用 var 声明

```javascript
// ✗ 错误
var x = 1;

// ✓ 正确
const x = 1;
let y = 2;
```

**原因：** `var` 有变量提升和函数作用域问题。

---

### for-in 循环

```javascript
// ✗ 错误 - for-in 遍历原型链
for (const key in obj) {
    console.log(obj[key]);
}

// ✓ 正确 - for-of
for (const [key, value] of Object.entries(obj)) {
    console.log(key, value);
}

// ✓ 正确 - Object.keys
Object.keys(obj).forEach(key => {
    console.log(obj[key]);
});
```

---

### then 链式调用

```javascript
// ✗ 错误 - 难以阅读和调试
fetch(url)
    .then(response => response.json())
    .then(data => {
        console.log(data);
        return processData(data);
    })
    .catch(error => console.error(error));

// ✓ 正确 - async/await
async function fetchData() {
    try {
        const response = await fetch(url);
        const data = await response.json();
        console.log(data);
        return processData(data);
    } catch (error) {
        console.error('请求失败:', error);
        throw error;
    }
}
```

---

## 线程安全

### 数据竞争

```c
// ✗ 错误 - 多线程访问无保护
static int g_counter = 0;

void increment(void) {
    g_counter++;  // 数据竞争！
}

// ✓ 正确 - 加锁
static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
static int g_counter = 0;

void increment(void) {
    pthread_mutex_lock(&g_lock);
    g_counter++;
    pthread_mutex_unlock(&g_lock);
}
```

---

### 条件变量虚假唤醒

```c
// ✗ 错误 - 条件检查在循环外
pthread_cond_wait(&cond, &mutex);
if (ready) {  // 可能是虚假唤醒
    process();
}

// ✓ 正确 - 条件检查在循环内
while (!ready) {  // 循环检查
    pthread_cond_wait(&cond, &mutex);
}
process();  // 确认 ready
```

---

## 常见编译错误

### undefined reference

```bash
# 错误信息
undefined reference to `agent_init'

# 原因：链接顺序错误

# ✗ 错误
gcc -o agent main.c -L. -lagent

# ✓ 正确 - 库在源文件后面
gcc -o agent main.c -lagent
```

---

### implicit declaration

```bash
# 错误信息
warning: implicit declaration of function 'agent_init'

# 原因：缺少头文件

# ✓ 解决
#include "agent.h"
```

---

### 静态分析误报

```bash
# cppcheck 可能误报
# "condition is always true"

# 解决方案：添加抑制注释
// cppcheck-suppress knownConditionTrueFalse
if (ptr != NULL) {  // 防御性检查
    free(ptr);
}
```

---

## 快速排查清单

| 问题类型 | 检查项 |
|----------|--------|
| 编译失败 | cmake 参数、头文件、链接顺序 |
| 运行崩溃 | malloc 返回值、空指针、数组越界 |
| 内存泄漏 | 所有分配路径都有释放 |
| 协议错误 | 三处同步：agent.h、constants.py、PROTOCOL.md |
| 测试失败 | 查看错误信息、检查边界情况 |
| 性能问题 | 循环中是否有不必要的操作 |

---

## 调试技巧

### C 代码调试

```bash
# 编译时加调试符号
cmake .. -DCMAKE_BUILD_TYPE=Debug

# 使用 gdb
gdb ./bin/buildroot-agent
(gdb) run -c config.yaml

# 检查内存泄漏
valgrind --leak-check=full ./bin/buildroot-agent -c config.yaml
```

### Python 调试

```bash
# 详细日志
uv run python main.py --log-level DEBUG

# 进入调试器
import pdb; pdb.set_trace()

# 或使用 breakpoint() (Python 3.7+)
breakpoint()
```

### 网络调试

```bash
# 抓包分析
tcpdump -i any port 8766 -w agent.pcap

# 查看 WebSocket
websocket-client --connect ws://localhost:8765

# 测试 TCP 连接
nc -v localhost 8766
```