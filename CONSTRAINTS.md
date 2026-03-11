# CONSTRAINTS.md - 硬约束

> **警告：违反以下约束将导致构建失败或运行时错误**
> 
> 所有代码修改必须遵守这些限制。

---

## 运行环境约束

### 编译环境

| 约束 | 值 | 原因 |
|------|-----|------|
| cmake 版本 | ≥ 2.8.12.2 | 嵌入式环境限制 |
| gcc 版本 | ≥ 4.9 | buildroot 2015.08.1 |
| openssl 版本 | ≥ 1.1.1 | 安全要求 |

### 运行环境

| 约束 | 值 | 原因 |
|------|-----|------|
| buildroot | 2015.08.1 | 目标平台 |
| 内核版本 | 无限制 | 兼容性 |

---

## CMake 约束

### 禁止使用的参数

```bash
# ✗ 错误 - cmake 2.8.12 不支持
cmake -B build
cmake -S . -B build

# ✓ 正确
mkdir -p build && cd build && cmake ..
```

**原因：** cmake 2.8.12 版本太老，不支持 `-B` 和 `-S` 参数。

### 必须使用的参数

```bash
# 静态链接（嵌入式环境推荐）
cmake .. -DSTATIC_LINK=ON

# 交叉编译
cmake .. -DCMAKE_TOOLCHAIN_FILE=cmake/arm-buildroot.cmake
```

---

## 协议约束

### 消息大小

| 约束 | 值 | 原因 |
|------|-----|------|
| 最大消息大小 | 64KB (65535 字节) | 协议头 2 字节长度限制 |
| Base64 分块 | ≤ 48KB | 预留头部空间 |
| 文件列表分块 | ≤ 20 文件/块 | 避免超限 |

### 消息类型同步

**修改消息类型必须同步三处：**

| 语言 | 文件 | 定义方式 |
|------|------|----------|
| C | `buildroot-agent/include/agent.h` | `msg_type_t` 枚举 |
| Python | `buildroot-server/protocol/constants.py` | `MessageType` IntEnum |
| 文档 | `PROTOCOL.md` | 消息定义章节 |

**不同步将导致：**
- 编译错误（如果只是新增）
- 运行时消息解析错误（如果修改现有类型）
- Agent/Server 通信失败

### 响应类型约束

```
Web 查询系统状态时：

✗ 错误 - Agent 返回 SYSTEM_STATUS (0x02)
  → Web 无法通过 request_id 路由响应

✓ 正确 - Agent 返回 CMD_RESPONSE (0x31)
  → 包含 request_id，Server 可正确路由
```

**原因：** SYSTEM_STATUS 是主动上报，无 request_id；Web 查询需要 request_id 进行响应路由。

---

## C 代码约束

### 内存管理

| 约束 | 原因 |
|------|------|
| 必须检查 malloc/calloc 返回值 | 嵌入式环境内存紧张，分配可能失败 |
| 禁止重复释放 (double free) | 未定义行为 |
| 禁止内存泄漏 | 长期运行的守护进程 |
| 禁止使用 strcpy | 缓冲区溢出风险 |
| 禁止使用 sprintf | 缓冲区溢出风险 |

```c
// ✗ 错误
char *buf = malloc(size);
// 直接使用，未检查

// ✓ 正确
char *buf = malloc(size);
if (buf == NULL) {
    LOG_ERROR("malloc failed");
    return -1;
}
// 使用 buf
free(buf);
```

### 字符串操作

```c
// ✗ 错误
strcpy(dest, src);
sprintf(buf, "value: %d", val);

// ✓ 正确
safe_strncpy(dest, src, sizeof(dest));
snprintf(buf, sizeof(buf), "value: %d", val);
```

### 文件操作

| 约束 | 原因 |
|------|------|
| 追加模式 `"ab"` 中 fseek 无效 | C 标准行为 |
| 使用 `"r+b"` 进行随机读写 | 正确的模式 |

```c
// ✗ 错误 - 追加模式下 fseek 无效
FILE *fp = fopen(path, "ab");
fseek(fp, offset, SEEK_SET);  // 无效！

// ✓ 正确 - 使用 r+b 模式
FILE *fp = fopen(path, "r+b");
fseek(fp, offset, SEEK_SET);  // 有效
```

### 线程安全

| 约束 | 原因 |
|------|------|
| 共享变量访问必须加锁 | 数据竞争 |
| 条件检查在循环内外都要做 | 虚假唤醒 |

```c
// ✗ 错误 - 无锁访问
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

## Python 代码约束

### 异常处理

```python
# ✗ 禁止 - 吞掉所有异常
try:
    do_something()
except:
    pass

# ✗ 禁止 - 裸 except
except:
    log_error()

# ✓ 正确 - 明确异常类型
try:
    do_something()
except ValueError as e:
    logger.error(f"值错误: {e}")
except Exception as e:
    logger.error(f"未知错误: {e}")
    raise
```

### 导入

```python
# ✗ 禁止 - 通配符导入
from module import *

# ✓ 正确 - 明确导入
from module import func1, func2, ClassA
```

### 未使用代码

```bash
# 运行 ruff 检查
uv run ruff check .

# F401 - 未使用的导入（必须删除）
# F841 - 未使用的变量（必须删除）
```

---

## JavaScript 代码约束

### 变量声明

```javascript
// ✗ 禁止
var x = 1;

// ✓ 正确
const x = 1;
let y = 2;
```

### 异步代码

```javascript
// ✗ 禁止 - then 链
fetch(url)
    .then(response => response.json())
    .then(data => processData(data));

// ✓ 正确 - async/await
async function fetchData() {
    const response = await fetch(url);
    const data = await response.json();
    return processData(data);
}
```

### 循环

```javascript
// ✗ 禁止 - for-in
for (const key in obj) {
    console.log(obj[key]);
}

// ✓ 正确 - for-of
for (const [key, value] of Object.entries(obj)) {
    console.log(key, value);
}
```

---

## 端口约束

| 端口 | 用途 | 协议 |
|------|------|------|
| 8765 | Web ↔ Server | WebSocket |
| 8766 | Agent ↔ Server | TCP Socket |

**修改端口需同步更新：**
- Server 配置 (`config/settings.py`)
- Agent 配置 (`config.yaml` 或环境变量)
- Web 配置 (`js/config.js`)
- 文档 (`PROTOCOL.md`)

---

## 数据库约束

| 环境 | 数据库 | 建表方式 |
|------|--------|----------|
| 开发/测试 | SQLite | 自动建表 |
| 生产 | PostgreSQL/MySQL | 手动建表或 schema.sql |

**注意：** 生产环境必须提前建表，程序不会自动创建。

---

## 版本号约束

| 格式 | 示例 | 说明 |
|------|------|------|
| `主版本.次版本.修订版本` | `1.2.3` | 语义化版本 |

| 修改类型 | 版本变化 |
|----------|----------|
| Bug 修复 | 修订版本 +1 |
| 新功能 | 次版本 +1 |
| 重大变更 | 主版本 +1 |

**版本文件位置：** `buildroot-agent/VERSION`

---

## 测试约束

| 要求 | 值 |
|------|-----|
| Server 测试覆盖率 | ≥ 40% |
| 所有测试 | 必须通过 |
| 新功能 | 必须添加测试 |

---

## 违反约束的后果

| 约束类型 | 后果 |
|----------|------|
| cmake 参数错误 | 构建失败 |
| 协议不同步 | 通信失败 |
| 内存检查缺失 | 运行时崩溃 |
| 异常吞掉 | 问题难以排查 |
| 测试失败 | CI 不通过，无法合并 |

---

## 检查清单

修改代码前确认：

- [ ] cmake 版本兼容（无 -B 参数）
- [ ] 消息类型同步（三处）
- [ ] 内存分配检查
- [ ] 字符串使用安全版本
- [ ] 异常处理明确类型
- [ ] 测试通过