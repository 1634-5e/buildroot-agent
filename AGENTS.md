# AGENTS.md - AI 编码助手指南

> **目标：** 让不太可靠的模型也能稳定完成任务

---

## 工作流程

### 第一步：检查是否需要拆解

**触发条件（满足任一）：**
- 需要修改 ≥3 个文件
- 涉及 ≥2 个组件（Agent/Server/Web）
- 预估代码 ≥200 行

**需要拆解时：**
```
1. 停止！输出拆解计划
2. 等待用户确认
3. 逐个执行子任务
```

**拆解模板：**
```markdown
## 任务拆解

**原始任务：** [用户描述]

**子任务：**
1. [名称] - [文件] - ~[N]行 - [依赖]
2. [名称] - [文件] - ~[N]行 - [依赖]

**执行顺序：** 1 → 2 → 3

**是否开始？**
```

### 第二步：实现前输出计划

```markdown
## 实现计划

- **修改文件：** [具体路径]
- **改动内容：** [简要描述]
- **测试方法：** [TC-XXX 或手动测试]
```

### 第三步：写代码后自检

```
□ 函数长度 < 50行
□ 无重复代码
□ 边界情况已处理
□ 运行测试：./scripts/test.sh --<component>
```

---

## 硬约束（违反必失败）

### CMake
```bash
# ✗ cmake 2.8.12 不支持
cmake -B build

# ✓ 正确
mkdir -p build && cd build && cmake ..
```

### C 代码
```c
// ✗ 禁止
strcpy(dest, src);
char *buf = malloc(size); // 未检查

// ✓ 正确
safe_strncpy(dest, src, sizeof(dest));
char *buf = malloc(size);
if (!buf) return -1;
```

### Python 代码
```python
# ✗ 禁止
except: pass

# ✓ 正确
except ValueError as e:
    logger.error(f"错误: {e}")
```

### 协议同步
新增消息类型必须同步三处：
1. `buildroot-agent/include/agent.h` - `msg_type_t`
2. `buildroot-server/protocol/constants.py` - `MessageType`
3. `PROTOCOL.md` - 消息定义

---

## 常见错误对照

| 错误 | 正确 | 原因 |
|------|------|------|
| `cmake -B build` | `mkdir -p build && cd build && cmake ..` | cmake 2.8.12 版本限制 |
| Agent 响应 status 返回 `SYSTEM_STATUS` | 返回 `CMD_RESPONSE` | Web 需要 request_id 路由 |
| `strcpy(dest, src)` | `safe_strncpy(dest, src, sizeof(dest))` | 缓冲区溢出风险 |
| `except: pass` | `except ValueError as e:` | 吞掉错误 |
| `sessionId` | `session_id` | 统一 snake_case |

---

## 架构速览

```
┌─────────────┐   TCP:8766   ┌─────────────┐   WS:8765   ┌─────────────┐
│   Agent     │◄────────────►│   Server    │◄───────────►│    Web      │
│  (C语言)    │              │  (Python)   │             │  (JS/Vue)   │
└─────────────┘              └─────────────┘             └─────────────┘
```

**运行环境：** buildroot 2015.08.1, gcc 4.9, cmake 2.8.12.2

---

## 构建命令

```bash
# Agent
cd buildroot-agent && mkdir -p build && cd build && cmake .. && make

# Server
cd buildroot-server && uv run python main.py

# 测试
./scripts/test.sh
```

---

## 代码规范

### 函数长度
- 目标：< 30 行
- 上限：50 行

### 命名
| 语言 | 类型 | 风格 | 示例 |
|------|------|------|------|
| C | 函数/变量 | snake_case | `agent_init` |
| C | 宏/枚举 | UPPER_CASE | `MSG_TYPE_HEARTBEAT` |
| Python | 函数/变量 | snake_case | `handle_connection` |
| Python | 类 | PascalCase | `CloudServer` |
| JS | 函数/变量 | camelCase | `sendMessage` |

### 错误处理
- C：返回 0=成功，-1=错误
- Python：抛出明确异常类型
- JS：async/await + try/catch

---

## 更多细节

- [STYLE.md](STYLE.md) - 完整代码规范
- [BUILD.md](BUILD.md) - 详细构建命令
- [TESTING.md](TESTING.md) - 测试用例清单
- [PROTOCOL.md](PROTOCOL.md) - 通信协议规范