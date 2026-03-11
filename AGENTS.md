# AGENTS.md - AI 编码助手指南

> **目标：** 让不太可靠的模型也能稳定完成任务

---

## 当前任务

<!--
模型可以在这里记录当前任务的进度。
开始新任务时，先清理旧内容。
-->

```
[等待新任务]
```

---

## 工作流程

### 第一步：检查是否需要拆解

**触发条件（满足任一）：**
- 需要修改 ≥3 个文件
- 涉及 ≥2 个组件（Agent/Server/Web）
- 预估代码 ≥200 行

**拆解模板：**
```markdown
## 任务拆解

**原始任务：** [用户描述]

**子任务：**
1. [名称] - [文件] - ~[N]行
2. [名称] - [文件] - ~[N]行

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

### 第三步：完成后自检

```
□ 函数长度 < 50行
□ 无重复代码
□ 边界情况已处理
□ 运行测试通过
```

---

## 硬约束

### CMake
```bash
# 禁止
cmake -B build

# 正确
mkdir -p build && cd build && cmake ..
```

### 协议同步
新增消息类型必须同步三处：
1. `buildroot-agent/include/agent.h`
2. `buildroot-server/protocol/constants.py`
3. `PROTOCOL.md`

### 响应类型
```
Web 查询状态时：
  禁止：Agent 返回 SYSTEM_STATUS (0x02)
  正确：Agent 返回 CMD_RESPONSE (0x31)
```

---

## 禁止

| 禁止 | 原因 |
|------|------|
| `cmake -B build` | cmake 2.8.12 不支持 |
| `strcpy(dest, src)` | 缓冲区溢出 |
| `except: pass` | 吞掉错误 |
| `var x = 1` | JavaScript 作用域问题 |
| 跳过测试 | CI 不通过 |
| 合并失败的 PR | 违反仓库规则 |

---

## 常见错误对照

| 错误 | 正确 | 原因 |
|------|------|------|
| `cmake -B build` | `mkdir -p build && cd build && cmake ..` | 版本限制 |
| Agent 返回 `SYSTEM_STATUS` | 返回 `CMD_RESPONSE` | 需要 request_id |
| `strcpy` | `safe_strncpy` | 缓冲区溢出 |
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

**版本号：** `buildroot-agent/VERSION`（格式：主版本.次版本.修订版本）

**CI 要求：** Server 66个测试、Agent 2个测试、覆盖率 ≥40%

---

## 项目目录

```
buildroot-agent/
├── buildroot-agent/     # C Agent（嵌入式设备端）
│   ├── include/         # 头文件 (agent.h)
│   └── src/             # 源代码 (agent_*.c)
├── buildroot-server/    # Python Server（中央服务器）
│   ├── handlers/        # 消息处理器
│   └── protocol/        # 协议定义
├── buildroot-web/       # Web 控制台
└── scripts/             # 构建/测试脚本
```

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

## 代码规范（精简）

| 规则 | 要求 |
|------|------|
| 函数长度 | < 50 行 |
| 命名 | snake_case（C/Python），camelCase（JS） |
| 错误处理 | C: 返回码；Python: 异常；JS: async/await |

---

## 按需参考

| 文档 | 内容 | 何时读取 |
|------|------|----------|
| [STYLE.md](STYLE.md) | 详细代码规范 | 不确定编码风格时 |
| [BUILD.md](BUILD.md) | 详细构建命令 | 编译/运行问题时 |
| [TESTING.md](TESTING.md) | 测试详情 | 添加测试时 |
| [PROTOCOL.md](PROTOCOL.md) | 通信协议 | 涉及消息类型时 |

---

## 学习记录

<!--
记录用户反馈的错误和教训，避免重复犯错。
-->

### 用户指定
- [等待用户补充]

### AI 学习
- [等待任务中学习]