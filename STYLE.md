# STYLE.md - 代码规范

> 严格遵守规范，确保代码一致性和可维护性。

---

## 通用原则

### 函数长度
- **目标：** < 30 行
- **上限：** 50 行（超过必须拆分）

### 命名原则
- 描述"做什么"，不是"怎么做"
- 禁止单字母变量（循环变量除外）
- 禁止缩写（除非是通用缩写如 id, url）

### 代码复杂度
- 嵌套深度 ≤ 2 层
- 每个函数只做一件事
- 无重复代码（DRY 原则）

### 注释
- 只解释"为什么"（设计决策、业务原因）
- 不解释"是什么"（代码应该自解释）
- 函数注释说明：参数、返回值、错误处理

---

## C 代码规范 (buildroot-agent)

### 命名约定

| 类型 | 风格 | 示例 |
|------|------|------|
| 类型/结构体 | `snake_case_t` | `agent_context_t` |
| 枚举/宏 | `UPPER_CASE` | `MSG_TYPE_HEARTBEAT` |
| 函数 | `snake_case()` | `agent_init()` |
| 全局变量 | `g_prefix_` | `g_agent_ctx` |
| 局部变量 | `snake_case` | `bytes_read` |

### 头文件组织

```c
#ifndef AGENT_H
#define AGENT_H

/* 标准库 */
#include <stdint.h>
#include <pthread.h>

/* 第三方库 */
#include <openssl/ssl.h>

/* 本地头文件 */
#include "config.h"

/* 宏定义 */
#define MAX_BUFFER_SIZE 4096

/* 类型定义 */
typedef struct agent_context {
    int socket_fd;
    char device_id[64];
} agent_context_t;

/* 函数声明 */
int agent_init(agent_context_t *ctx);
void agent_cleanup(agent_context_t *ctx);

#endif /* AGENT_H */
```

### 内存管理

**必须检查返回值：**
```c
/* ✓ 正确 */
void *buffer = malloc(size);
if (buffer == NULL) {
    LOG_ERROR("malloc failed: %s", strerror(errno));
    return -1;
}
/* 使用 buffer */
free(buffer);

/* ✗ 错误 */
void *buffer = malloc(size);
/* 直接使用，未检查 */
```

**使用 goto error 模式清理资源：**
```c
int process_file(const char *path) {
    FILE *fp = NULL;
    char *buffer = NULL;
    int result = -1;
    
    fp = fopen(path, "r");
    if (!fp) {
        LOG_ERROR("fopen failed: %s", strerror(errno));
        goto error;
    }
    
    buffer = malloc(BUFFER_SIZE);
    if (!buffer) {
        LOG_ERROR("malloc failed");
        goto error;
    }
    
    /* 处理逻辑 */
    result = 0;
    
error:
    if (buffer) free(buffer);
    if (fp) fclose(fp);
    return result;
}
```

### 字符串操作

```c
/* ✓ 正确 - 使用安全版本 */
safe_strncpy(dest, src, sizeof(dest));
snprintf(buf, sizeof(buf), "value: %d", val);

/* ✗ 错误 - 危险函数 */
strcpy(dest, src);
sprintf(buf, "value: %d", val);
```

### 错误处理

```c
/* 返回值约定 */
// 0  = 成功
// -1 = 错误（查看 errno 或日志）
// >0 = 部分成功（如读写字节数）

int send_message(agent_context_t *ctx, const uint8_t *data, size_t len) {
    if (!ctx || !data) {
        LOG_ERROR("invalid parameters");
        return -1;
    }
    
    ssize_t sent = send(ctx->socket_fd, data, len, 0);
    if (sent < 0) {
        LOG_ERROR("send failed: %s", strerror(errno));
        return -1;
    }
    
    return (int)sent;
}
```

### 日志规范

```c
LOG_DEBUG("调试信息: %d", value);      // 开发调试
LOG_INFO("设备连接: %s", device_id);    // 正常事件
LOG_WARN("配置缺失，使用默认值");        // 警告
LOG_ERROR("发送失败: %s", strerror(errno));  // 错误
```

### 线程安全

```c
/* 共享变量必须加锁 */
static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
static int g_counter = 0;

void increment_counter(void) {
    pthread_mutex_lock(&g_lock);
    g_counter++;
    pthread_mutex_unlock(&g_lock);
}
```

### 类型安全

```c
/* ✓ 正确 - 使用 enum */
typedef enum {
    UPDATE_STATE_IDLE = 0,
    UPDATE_STATE_DOWNLOADING = 1,
    UPDATE_STATE_INSTALLING = 2,
} update_state_t;

/* ✗ 错误 - 使用 #define */
#define UPDATE_STATE_IDLE 0
#define UPDATE_STATE_DOWNLOADING 1
```

```c
/* ✓ 正确 - const 修饰只读参数 */
int process_data(const char *input, size_t len);

/* ✓ 正确 - 限制性指针（减少别名） */
void copy_data(char * restrict dest, const char * restrict src, size_t n);
```

---

## Python 代码规范 (buildroot-server)

### 命名约定

| 类型 | 风格 | 示例 |
|------|------|------|
| 类 | `PascalCase` | `CloudServer` |
| 函数/方法 | `snake_case` | `handle_connection` |
| 变量 | `snake_case` | `device_list` |
| 常量 | `UPPER_CASE` | `MAX_MESSAGE_SIZE` |
| 私有 | `_prefix` | `_get_remote_address` |

### 导入顺序

```python
# 1. 标准库
import asyncio
import logging
from typing import Optional, Any

# 2. 第三方库
from pydantic import BaseModel, Field

# 3. 本地模块
from config.settings import settings
from protocol.constants import MessageType
```

### 类型注解

```python
# 公开 API 必须有类型注解
def get_device(self, device_id: str) -> dict[str, Any] | None:
    """获取设备信息。
    
    Args:
        device_id: 设备ID
        
    Returns:
        设备信息字典，如果不存在返回 None
    """
    return self._devices.get(device_id)


# 变量类型注解
devices: dict[str, dict[str, Any]] = {}
message_count: int = 0
```

### 错误处理

```python
# ✓ 正确 - 明确的异常类型
async def send_message(self, data: bytes) -> None:
    try:
        await self.websocket.send(data)
    except WebSocketDisconnect:
        logger.warning("客户端断开连接")
        raise
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        raise


# ✗ 错误 - 吞掉异常
try:
    do_something()
except:  # 禁止！
    pass


# ✗ 错误 - 裸 except
except:
    logger.error("error")


# ✓ 正确 - 使用自定义异常
class DeviceNotFoundError(Exception):
    """设备不存在"""
    pass


def get_device_or_raise(device_id: str) -> dict[str, Any]:
    device = get_device(device_id)
    if device is None:
        raise DeviceNotFoundError(f"设备不存在: {device_id}")
    return device
```

### 数据模型

```python
from pydantic import BaseModel, Field
from datetime import datetime


class Device(BaseModel):
    """设备信息模型"""
    device_id: str = Field(..., description="设备唯一标识")
    name: str | None = Field(None, description="设备名称")
    ip_addr: str = Field(..., description="IP地址")
    status: str = Field("offline", description="状态")
    last_seen: datetime | None = Field(None, description="最后在线时间")


# 使用
device = Device(
    device_id="device-001",
    ip_addr="192.168.1.100",
    status="online"
)
print(device.model_dump_json())
```

### 日志规范

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("调试信息")
logger.info(f"设备连接: {device_id}")
logger.warning("配置缺失，使用默认值")
logger.error(f"处理失败: {e}", exc_info=True)
```

### 异步代码

```python
# ✓ 正确 - async/await
async def handle_connection(websocket: WebSocket) -> None:
    async for message in websocket.iter_messages():
        await process_message(message)


# ✗ 错误 - .then() 链式调用
def handle_connection(websocket):
    return websocket.receive().then(process_message)
```

### 上下文管理器

```python
from contextlib import contextmanager

@contextmanager
def temp_file(path: str):
    """临时文件上下文管理器"""
    f = open(path, 'w')
    try:
        yield f
    finally:
        f.close()
        os.remove(path)


# 使用
with temp_file('/tmp/test.txt') as f:
    f.write('hello')
# 文件自动删除
```

---

## JavaScript 代码规范 (buildroot-web)

### 命名约定

| 类型 | 风格 | 示例 |
|------|------|------|
| 类 | `PascalCase` | `WebSocketClient` |
| 函数 | `camelCase` | `sendMessage` |
| 变量 | `camelCase` | `deviceId` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_RECONNECT_DELAY` |
| 私有 | `_prefix` | `_handleMessage` |

### 变量声明

```javascript
// ✓ 正确
const MAX_SIZE = 1024;
let messageCount = 0;

// ✗ 错误
var x = 1;  // 禁止使用 var
```

### 异步代码

```javascript
// ✓ 正确 - async/await
async function fetchDevices() {
    try {
        const response = await fetch('/api/devices');
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('获取设备列表失败:', error);
        throw error;
    }
}

// ✗ 错误 - .then() 链
function fetchDevices() {
    return fetch('/api/devices')
        .then(response => response.json())
        .then(data => data)
        .catch(error => console.error(error));
}
```

### 对象解构

```javascript
// ✓ 正确
const { device_id, status, ip_addr } = device;
const { deviceId: id, ...rest } = device;

// ✗ 错误
const deviceId = device.deviceId;
const status = device.status;
```

### 循环

```javascript
// ✓ 正确 - for-of
for (const device of devices) {
    console.log(device.device_id);
}

// ✓ 正确 - forEach
devices.forEach(device => console.log(device.device_id));

// ✓ 正确 - map/filter
const onlineDevices = devices.filter(d => d.status === 'online');
const deviceIds = devices.map(d => d.device_id);

// ✗ 错误 - for-in
for (const key in devices) {  // 禁止
    console.log(devices[key]);
}
```

### DOM 操作

```javascript
// ✓ 正确 - 使用现代 API
const element = document.querySelector('.device-card');
const elements = document.querySelectorAll('.device-card');

// 设置内容
element.textContent = 'Hello';
element.innerHTML = '<span>Hello</span>';

// 添加事件
element.addEventListener('click', (event) => {
    console.log('clicked', event.target);
});

// ✓ 正确 - classList
element.classList.add('active');
element.classList.remove('inactive');
element.classList.toggle('selected');
```

### 模块导出

```javascript
// 导出函数
export function sendMessage(data) { ... }

// 导出常量
export const MAX_RETRIES = 3;

// 默认导出
export default class WebSocketClient { ... }

// 导入
import { sendMessage, MAX_RETRIES } from './websocket.js';
import WebSocketClient from './websocket.js';
```

---

## Vue 组件规范 (buildroot-web-vue)

### 组件结构

```vue
<template>
  <div class="device-card">
    <h3>{{ device.name }}</h3>
    <span :class="statusClass">{{ device.status }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  device: {
    type: Object,
    required: true
  }
})

const statusClass = computed(() => ({
  'status-online': props.device.status === 'online',
  'status-offline': props.device.status === 'offline'
}))
</script>

<style scoped>
.device-card {
  padding: 16px;
  border: 1px solid #ddd;
}
.status-online { color: green; }
.status-offline { color: red; }
</style>
```

### Props 定义

```javascript
// ✓ 正确 - 完整定义
const props = defineProps({
  deviceId: {
    type: String,
    required: true
  },
  status: {
    type: String,
    default: 'offline'
  }
})

// ✗ 错误 - 简写（类型不明确）
const props = defineProps(['deviceId', 'status'])
```

### Emits 定义

```javascript
// ✓ 正确 - 明确事件
const emit = defineEmits(['connect', 'disconnect'])

function handleConnect() {
  emit('connect', props.deviceId)
}
```

---

## 代码格式化

### C 代码
```bash
# 使用 clang-format（如果有）
clang-format -i src/*.c
```

### Python 代码
```bash
cd buildroot-server
uv run ruff format .
uv run ruff check . --fix
```

### JavaScript 代码
```bash
# 使用 prettier（如果有）
prettier --write "js/**/*.js"
```

---

## 提交前检查

```bash
# C 代码
cd buildroot-agent
mkdir -p build && cd build && cmake ..
make
# 检查是否有警告

# Python 代码
cd buildroot-server
uv run ruff check .
uv run ruff format --check .

# 运行测试
./scripts/test.sh
```