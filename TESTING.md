# TESTING.md - 测试文档

## 测试架构

**三端全覆盖真实场景测试：**

| 端 | 框架 | 测试数量 | 覆盖率要求 |
|----|------|----------|------------|
| Server | pytest + pytest-asyncio | 66 个 | ≥ 40% |
| Agent | CMocka + Shell | 2 个 | 核心功能覆盖 |
| Web | pytest | 20 个 | 静态文件检查 |

---

## 测试用例清单

### 连接测试 (TC-CONN)

| ID | 测试项 | 描述 | 状态 |
|----|--------|------|------|
| TC-CONN-001 | Server 启动 | 启动 Python Server，端口监听成功 | ✓ |
| TC-CONN-002 | Agent 连接 | Agent 成功连接到 Server | ✓ |
| TC-CONN-003 | 设备注册 | Agent 发送 REGISTER，返回 REGISTER_RESULT | ✓ |
| TC-CONN-004 | 心跳机制 | Agent 每 30 秒发送心跳 | ✓ |
| TC-CONN-005 | 自动重连 | Server 重启后 Agent 自动重连 | ✓ |
| TC-CONN-006 | 连接超时 | 90 秒无心跳自动断开 | ✓ |
| TC-CONN-007 | 多 Agent 连接 | 多个 Agent 同时连接 Server | ✓ |

### 状态测试 (TC-STATUS)

| ID | 测试项 | 描述 | 状态 |
|----|--------|------|------|
| TC-STATUS-001 | 系统状态上报 | 自动上报 CPU/内存/磁盘等信息 | ✓ |
| TC-STATUS-002 | 状态字段完整性 | 验证所有状态字段正确上报 | ✓ |
| TC-STATUS-003 | Web 主动查询 | Web 查询状态返回 CMD_RESPONSE | ✓ |

### PTY 测试 (TC-PTY)

| ID | 测试项 | 描述 | 状态 |
|----|--------|------|------|
| TC-PTY-001 | 创建会话 | Web 创建终端会话 | ✓ |
| TC-PTY-002 | 数据收发 | 终端输入命令并接收输出 | ✓ |
| TC-PTY-003 | 窗口调整 | 调整浏览器窗口大小 | ✓ |
| TC-PTY-004 | 会话超时 | 30 分钟无活动自动关闭 | ✓ |
| TC-PTY-005 | 关闭会话 | 关闭终端会话 | ✓ |

### 文件测试 (TC-FILE)

| ID | 测试项 | 描述 | 状态 |
|----|--------|------|------|
| TC-FILE-001 | 文件上传 | 上传文件到 Agent | ✓ |
| TC-FILE-002 | 文件下载 | 从 Agent 下载文件 | ✓ |
| TC-FILE-003 | 文件列表 | 获取目录文件列表 | ✓ |
| TC-FILE-004 | 文件读取 | 读取文件内容 | ✓ |
| TC-FILE-005 | 文件写入 | 写入文件内容 | ✓ |
| TC-FILE-006 | 文件监控 | 监控文件变化 | ✓ |

### 命令测试 (TC-CMD)

| ID | 测试项 | 描述 | 状态 |
|----|--------|------|------|
| TC-CMD-001 | 命令执行 | 执行远程命令并返回结果 | ✓ |
| TC-CMD-002 | 错误处理 | 执行不存在命令返回错误 | ✓ |
| TC-CMD-003 | 内置命令 status | 查询系统状态 | ✓ |
| TC-CMD-004 | 内置命令 reboot | 重启设备 | ✓ |

### 更新测试 (TC-UPDATE)

| ID | 测试项 | 描述 | 状态 |
|----|--------|------|------|
| TC-UPDATE-001 | 版本检查 | 检查更新并返回版本信息 | ✓ |
| TC-UPDATE-002 | 下载流程 | 下载更新包并校验 | ✓ |
| TC-UPDATE-003 | 安装流程 | 安装更新并重启 | ✓ |
| TC-UPDATE-004 | 回滚流程 | 更新失败自动回滚 | ✓ |
| TC-UPDATE-005 | 批准流程 | Web 批准下载和安装 | ✓ |

### Ping 测试 (TC-PING)

| ID | 测试项 | 描述 | 状态 |
|----|--------|------|------|
| TC-PING-001 | 网络监控 | Ping 配置目标并上报状态 | ✓ |
| TC-PING-002 | 丢包检测 | 检测网络丢包率 | ✓ |

---

## 运行测试

### 统一测试脚本

```bash
# 运行全部测试
./scripts/test.sh

# 运行特定端测试
./scripts/test.sh --server    # 仅 Server 端
./scripts/test.sh --agent     # 仅 Agent 端
./scripts/test.sh --web       # 仅 Web 端

# 运行特定测试用例
./scripts/test.sh --test TC-CONN-003

# 生成覆盖率报告
./scripts/test.sh --report

# 调试模式（保留测试环境）
./scripts/test.sh --debug
```

### Server 端测试

```bash
cd buildroot-server

# 安装测试依赖
uv add --dev pytest pytest-asyncio pytest-html

# 运行所有测试
uv run pytest tests/ -v

# 运行特定测试
uv run pytest tests/test_integration.py -v
uv run pytest tests/ -v -k "test_register"

# 生成覆盖率报告
uv run pytest tests/ -v --html=report.html

# 详细输出
uv run pytest tests/ -v -s
```

### Agent 端测试

```bash
cd buildroot-agent/tests

# 运行 CMocka 单元测试
./run_tests.sh

# 使用 Mock Server 测试
python mock_server.py &
../build/bin/buildroot-agent -c test_agent.cfg
```

### Web 端测试

```bash
cd buildroot-web

# 检查静态文件
python -m pytest tests/test_static.py -v

# 完整测试（需 Server 运行）
python -m pytest tests/ -v
```

---

## 添加新测试

### Server 端测试模板

```python
# tests/handlers/test_new_feature.py
import pytest
from fixtures.mock_agent import MockAgent


@pytest.mark.asyncio
async def test_new_feature(mock_server):
    """TC-NEW-001: 新功能测试
    
    测试步骤：
    1. Agent 连接到 Server
    2. 发送特定消息
    3. 验证响应
    
    预期结果：返回正确的响应
    """
    agent = MockAgent()
    await agent.connect("127.0.0.1", 8766)
    
    # 执行测试
    result = await agent.send_message(MSG_TYPE_NEW, data)
    
    # 验证结果
    assert result["status"] == "success"
```

### Agent 端测试模板

```bash
#!/bin/bash
# tests/test_cases/test_new_feature.sh

source ../utils.sh

test_new_feature() {
    log "TC-NEW-001: 测试新功能"
    
    # 启动 Mock Server
    start_mock_server
    
    # 启动 Agent
    start_agent
    
    # 等待连接
    sleep 2
    
    # 发送测试消息
    send_message "test_data"
    
    # 验证结果
    assert_contains "$LOG_FILE" "处理成功"
    
    # 清理
    cleanup
}

run_test test_new_feature
```

---

## 测试数据

### Mock 数据位置

```
buildroot-server/tests/fixtures/
├── mock_agent.py      # Mock Agent 实现
├── sample_messages.py # 示例消息
└── test_config.yaml   # 测试配置
```

### 示例消息

```python
# tests/fixtures/sample_messages.py

REGISTER_MSG = {
    "device_id": "test-device-001",
    "version": "1.0.0"
}

HEARTBEAT_MSG = {
    "timestamp": 1708000000000,
    "uptime": 3600
}

SYSTEM_STATUS_MSG = {
    "cpu_usage": 45.2,
    "mem_total": 4096.0,
    "mem_used": 2048.0,
    "hostname": "test-device",
    "ip_addr": "192.168.1.100"
}
```

---

## 覆盖率要求

### Server 端

```bash
# 查看覆盖率
uv run pytest tests/ --cov=. --cov-report=html

# 要求
# - 总覆盖率 ≥ 40%
# - 核心模块覆盖率 ≥ 60%
# - 新功能必须添加测试
```

### Agent 端

```bash
# 使用 gcov（如果启用）
cd buildroot-agent/build
make coverage

# 要求
# - 核心功能有测试覆盖
# - 新功能必须添加测试
```

---

## CI/CD 集成

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test-server:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install uv
        uses: astral-sh/setup-uv@v4
        
      - name: Test Server
        run: |
          cd buildroot-server
          uv sync
          uv run pytest tests/ -v --cov=. --cov-report=xml
          
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./buildroot-server/coverage.xml

  test-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install dependencies
        run: |
          sudo apt-get install -y cmake gcc
        
      - name: Build Agent
        run: |
          cd buildroot-agent
          mkdir -p build && cd build
          cmake .. -DCMAKE_BUILD_TYPE=Debug
          make
          
      - name: Test Agent
        run: |
          cd buildroot-agent/tests
          ./run_tests.sh
```

---

## 测试最佳实践

### 1. 测试命名

```python
# ✓ 正确 - 描述性命名
def test_agent_register_success():
    """TC-CONN-003: 测试设备注册成功"""
    pass

def test_agent_register_with_invalid_device_id():
    """测试无效设备ID注册"""
    pass

# ✗ 错误 - 不清晰的命名
def test_register():
    pass

def test_case_1():
    pass
```

### 2. 测试隔离

```python
# ✓ 正确 - 每个测试独立
@pytest.fixture
async def mock_agent():
    agent = MockAgent()
    await agent.connect("127.0.0.1", 8766)
    yield agent
    await agent.disconnect()


async def test_feature(mock_agent):
    # 使用 fixture，测试后自动清理
    pass
```

### 3. 异步测试

```python
# ✓ 正确 - 使用 pytest-asyncio
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result is not None
```

### 4. 错误测试

```python
# ✓ 正确 - 测试错误情况
@pytest.mark.asyncio
async def test_connection_refused():
    with pytest.raises(ConnectionRefusedError):
        await connect_to_server("invalid-host", 9999)
```

---

## 调试测试

```bash
# 只运行失败的测试
uv run pytest tests/ -v --lf

# 在第一个失败处停止
uv run pytest tests/ -v -x

# 打印 print 输出
uv run pytest tests/ -v -s

# 进入调试器
uv run pytest tests/ -v --pdb
```