# Postmortem: 资源泄漏问题

**严重程度**: 🟡 P1 - 重要
**发现时间**: 2026-02-13 ~ 2026-02-14
**修复提交**: `4f6881e`, `d6e34fb`, `ee073b9`
**影响组件**: Server 端, Agent 端

---

## 问题概述

资源未正确释放导致内存泄漏、连接堆积、用户体验下降。

---

## 1. PTY 会话泄漏

### 根因分析

用户关闭/刷新网页时，PTY 终端会话未关闭，等待 30 分钟超时才释放：

```
用户行为:
  打开终端 → 建立 PTY 会话 → 刷新页面 → 旧会话残留
  
结果:
  - 服务端 PTY 进程堆积
  - 内存泄漏
  - 端口/文件描述符耗尽风险
```

### 代码问题

```python
# 问题代码
@app.websocket("/ws")
async def websocket_handler(websocket):
    await register_console(websocket)
    try:
        while True:
            data = await websocket.receive()
            await handle_message(data)
    except WebSocketDisconnect:
        pass  # 什么都没做！PTY 会话未清理
```

### 修复方案

```python
@app.websocket("/ws")
async def websocket_handler(websocket):
    console_id = await register_console(websocket)
    try:
        while True:
            data = await websocket.receive()
            await handle_message(data)
    except WebSocketDisconnect:
        # 发送 PTY_CLOSE 消息到 agent
        device_id, session_ids = await manager.remove_console(console_id)
        if device_id and session_ids:
            for session_id in session_ids:
                await send_pty_close(device_id, session_id, reason="console disconnected")
```

### 教训

1. **资源生命周期管理** - 每个资源获取都要有对应的释放逻辑
2. **异常处理完整性** - disconnect/timeout 都要清理
3. **资源追踪** - 知道哪些资源属于哪个连接

---

## 2. Web 控制台连接问题

### 根因分析

WebSocket 消息路由逻辑混乱，导致：
- 消息发送到错误的设备
- 终端无法连接
- SYSTEM_STATUS 消息丢失

```python
# 问题代码
async def broadcast_to_web_consoles(message):
    for console in web_consoles:
        await console.send(message)  # 广播给所有人！
```

**问题**：终端消息应该只发给特定设备的控制台，而非广播。

### 修复方案

```python
class ConnectionManager:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.console_info = {}  # console_id -> {device_id, sessions}
        self.request_sessions = {}  # request_id -> console_id
    
    async def send_to_device_console(self, device_id, message):
        async with self._lock:
            for console_id, info in self.console_info.items():
                if info.get("device_id") == device_id:
                    await self.web_consoles[console_id].send(message)
    
    async def unicast_by_request_id(self, request_id, message):
        """按 request_id 精准单播"""
        async with self._lock:
            console_id = self.request_sessions.get(request_id)
            if console_id:
                await self.web_consoles[console_id].send(message)
```

### 教训

1. **消息路由设计** - 明确单播、组播、广播的使用场景
2. **ID 关联** - 维护资源 ID 到连接的映射
3. **调试日志** - 复杂路由逻辑需要详细日志

---

## 3. 空目录加载卡死

### 根因分析

文件树展开空目录时，前端一直显示"加载中"：

```c
// 问题代码
int total_chunks = count / CHUNK_SIZE;  // count = 0 时，total_chunks = 0
for (int i = 0; i < total_chunks; i++) {
    // 循环不执行，不发送任何响应
}
```

**问题**：空目录时 `total_chunks = 0`，循环不执行，服务端不发送任何响应。

### 修复方案

```c
int total_chunks = (count == 0) ? 1 : (count / CHUNK_SIZE);
// 或更清晰：
int total_chunks = count / CHUNK_SIZE;
if (count == 0) {
    total_chunks = 1;  // 确保发送空响应
}
```

### 教训

1. **边界条件** - 空集合、零长度、首尾元素
2. **客户端超时处理** - 前端应有超时提示
3. **协议设计** - 空结果也要有明确响应

---

## 预防措施

### 立即实施

1. **资源审计** - 列出所有资源类型及其生命周期
2. **清理检查清单** - 每种断开方式都要检查清理逻辑

### 资源生命周期模板

```python
class ResourceManager:
    """资源生命周期管理模板"""
    
    async def acquire(self, resource_id, owner_id):
        """获取资源"""
        # 1. 创建资源记录
        # 2. 关联所有者
        # 3. 设置超时（可选）
        pass
    
    async def release(self, resource_id):
        """释放资源"""
        # 1. 查找资源
        # 2. 通知相关方
        # 3. 清理资源
        # 4. 移除记录
        pass
    
    async def release_by_owner(self, owner_id):
        """按所有者释放（断开连接时）"""
        resources = await self.list_by_owner(owner_id)
        for r in resources:
            await self.release(r.id)
```

### 测试覆盖

```python
@pytest.mark.asyncio
async def test_websocket_disconnect_cleans_up():
    """测试断开连接时资源清理"""
    ws = await connect_websocket()
    device_id = await open_terminal(ws)
    
    # 断开连接
    await ws.close()
    await asyncio.sleep(0.5)
    
    # 验证资源已清理
    assert not manager.has_device(device_id)
    assert not manager.has_active_pty(device_id)
```

---

## 相关提交

- `4f6881e` - PTY 会话清理修复
- `d6e34fb` - Web 控制台连接修复
- `ee073b9` - 空目录响应修复