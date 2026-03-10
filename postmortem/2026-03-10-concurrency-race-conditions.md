# Postmortem: 并发与竞态条件

**严重程度**: 🔴 P0 - 关键
**发现时间**: 2026-03-06
**修复提交**: `903567e`, `3779817`, `119c8e2`, `33d41ff`
**影响组件**: Server 端, 测试套件

---

## 问题概述

Server 端存在多处并发安全问题，导致多 Agent 注册时数据竞争、响应丢失、测试不稳定。

---

## 1. ConnectionManager 并发安全问题

### 根因分析

`managers/connection.py` 中的共享状态未加锁保护：

```python
# 危险代码
class ConnectionManager:
    def __init__(self):
        self.devices = {}  # 共享状态，无锁保护！
        self.web_consoles = []
    
    def add_device(self, device_id, websocket):
        self.devices[device_id] = websocket  # 多线程并发写入
        
    def get_device(self, device_id):
        return self.devices.get(device_id)  # 并发读取
```

**问题**：当多个 Agent 同时注册时，字典操作可能互相干扰，导致：
- 数据覆盖丢失
- KeyError 异常
- 状态不一致

### 触发条件

1. 多个 Agent 同时连接
2. CI 环境资源受限，并发更容易触发
3. 测试中模拟并发注册

### 修复方案

```python
import asyncio

class ConnectionManager:
    def __init__(self):
        self._lock = asyncio.Lock()  # 添加异步锁
        self.devices = {}
        self.web_consoles = []
    
    async def add_device(self, device_id, websocket):
        async with self._lock:  # 加锁保护
            self.devices[device_id] = websocket
    
    async def get_device(self, device_id):
        async with self._lock:
            return self.devices.get(device_id)
    
    async def remove_device(self, device_id):
        async with self._lock:
            self.devices.pop(device_id, None)
```

### 教训

1. **Python asyncio 并发风险** - 虽然单线程，但 await 点会切换，共享状态需保护
2. **显式加锁** - 不要依赖"很快完成"的假设
3. **测试覆盖** - 并发测试必须成为 CI 的一部分

---

## 2. Agent 注册响应丢失

### 根因分析

注册处理流程中，数据库操作阻塞了响应发送：

```python
# 问题代码
async def handle_register(websocket, data):
    # 1. 验证
    device = await validate_device(data)
    
    # 2. 数据库操作 - 耗时！
    await db.save_device(device)  # 阻塞
    
    # 3. 发送响应 - 太晚了！
    await websocket.send_json({"type": "register", "status": "ok"})
```

**问题**：Agent 端有超时机制，数据库操作延迟导致响应发送时 Agent 已断开。

### 修复方案

```python
async def handle_register(websocket, data):
    # 1. 验证
    device = await validate_device(data)
    
    # 2. 先发送响应
    await websocket.send_json({"type": "register", "status": "ok"})
    
    # 3. 后执行数据库操作
    await db.save_device(device)  # 异步后台任务
```

### 教训

1. **响应优先** - 用户/客户端等待的操作要尽快响应
2. **异步解耦** - 耗时操作放后台，不阻塞主流程
3. **超时考虑** - 设计时要考虑客户端超时时间

---

## 3. CI 测试竞态条件

### 根因分析

测试使用固定延迟等待异步操作，在不同环境表现不一致：

```python
# 问题代码
async def test_agent_registration():
    await agent.register()
    await asyncio.sleep(2)  # 固定延迟，不够可靠
    assert manager.get_device(device_id) is not None
```

**问题**：
- CI 环境可能比本地慢，2秒不够
- 本地环境可能比 CI 快，测试通过但实际有问题

### 修复方案

```python
async def test_agent_registration():
    await agent.register()
    
    # 轮询等待，带超时
    for _ in range(20):  # 最多等待 2 秒
        if manager.get_device(device_id) is not None:
            break
        await asyncio.sleep(0.1)
    else:
        raise TimeoutError("Registration timeout")
    
    assert manager.get_device(device_id) is not None
```

### 教训

1. **避免固定延迟** - 使用轮询/事件等待替代 sleep
2. **超时保护** - 所有等待操作都要有超时
3. **CI 环境差异** - 假设 CI 比本地慢 2-3 倍

---

## 预防措施

### 立即实施

1. **共享状态审查** - 检查所有共享数据结构是否有锁保护
2. **并发测试** - 添加多 Agent 并发注册测试用例
3. **延迟消除** - 替换所有测试中的固定延迟

### 代码模式

```python
# ✅ 正确的并发模式
class SharedResource:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._data = {}
    
    async def read(self, key):
        async with self._lock:
            return self._data.get(key)
    
    async def write(self, key, value):
        async with self._lock:
            self._data[key] = value

# ✅ 正确的测试等待模式
async def wait_for_condition(check_fn, timeout=5.0, interval=0.1):
    start = time.time()
    while time.time() - start < timeout:
        if await check_fn():
            return True
        await asyncio.sleep(interval)
    raise TimeoutError(f"Condition not met within {timeout}s")
```

---

## 相关提交

- `903567e` - ConnectionManager 并发安全修复
- `3779817` - 注册响应优化
- `119c8e2` - 测试竞态条件修复
- `33d41ff` - 轮询等待替代固定延迟