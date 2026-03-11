# AGENTS.md - AI 编码助手指南

> **适用模型：** 所有 AI 编码助手（包括较弱模型）
> **目标：** 即使是不太可靠的模型也能稳定产出高质量代码

---

## 快速索引

| 主题 | 文档 | 用途 |
|------|------|------|
| 任务拆解 | [TASK_DECOMPOSITION.md](TASK_DECOMPOSITION.md) | **大任务拆解规则** |
| 项目结构 | [ARCHITECTURE.md](ARCHITECTURE.md) | 目录结构、数据流、组件关系 |
| 代码规范 | [STYLE.md](STYLE.md) | C/Python/JS 编码规范 |
| 构建命令 | [BUILD.md](BUILD.md) | 编译、运行、打包命令 |
| 测试要求 | [TESTING.md](TESTING.md) | 测试用例、覆盖率、运行方式 |
| 硬约束 | [CONSTRAINTS.md](CONSTRAINTS.md) | **必须遵守的限制** |
| 通信协议 | [PROTOCOL.md](PROTOCOL.md) | 消息类型、格式、流程 |
| 常见错误 | [PITFALLS.md](PITFALLS.md) | 易错点、正确对照 |

---

## 工作流程（强制遵守）

### 0. 任务拆解检查（第一步！）

**触发拆解的条件（满足任一即拆解）：**
- 需要修改 ≥3 个文件
- 涉及 ≥2 个组件（Agent/Server/Web）
- 任务包含"和"、"并且"、"同时"等连接词
- 预估代码 ≥200 行
- 涉及协议变更

**拆解流程：**
```
1. 停止！不要直接开始实现
2. 输出拆解计划（使用 TASK_DECOMPOSITION.md 模板）
3. 等待用户确认
4. 按顺序执行子任务
5. 每个子任务完成后确认
```

**详见：** [TASK_DECOMPOSITION.md](TASK_DECOMPOSITION.md)

### 1. 接到任务后

```
□ 确认任务类型：新功能 / Bug修复 / 重构 / 文档
□ 确认影响组件：Agent / Server / Web / 多个
□ 读取相关文档：
    - 涉及协议 → PROTOCOL.md
    - 涉及架构 → ARCHITECTURE.md
    - 涉及编码 → STYLE.md
□ 检查约束 → CONSTRAINTS.md
```

### 2. 写代码前（必须输出）

```markdown
## 实现计划

- **修改文件：** [列出具体路径，如 buildroot-agent/src/agent_pty.c]
- **新增函数：** [函数名 + 职责，如 `handle_pty_resize() - 处理终端大小调整`]
- **修改函数：** [函数名 + 改动内容]
- **测试用例：** [TC-XXX-XXX，从 TESTING.md 选择]
- **风险点：** [可能影响的其他模块]
```

**注意：** 即使用户说"直接做"，也必须先输出计划，然后再写代码。

### 3. 写代码后（必须执行）

```
□ 运行测试：./scripts/test.sh --<component>
□ 检查警告：编译/运行时是否有新警告
□ 检查清单：见下方"代码质量清单"
□ 更新文档：如有协议变更，更新 PROTOCOL.md
```

### 4. 提交前

```
□ 所有测试通过
□ 无新增警告
□ 代码格式化完成
□ commit message 清晰
```

---

## 代码质量清单

### 写完代码后逐项检查

- [ ] 函数长度 < 30行（最大50行）
- [ ] 命名清晰：描述"做什么"而不是"怎么做"
- [ ] 无魔法数字/字符串（抽成常量）
- [ ] 嵌套深度 ≤ 2层
- [ ] 每个函数只做一件事
- [ ] 无重复代码
- [ ] 注释只解释"为什么"（不解释"是什么"）
- [ ] 边界情况已处理

### 按语言检查

**C 代码：**
- [ ] 所有 malloc/calloc 已检查返回值
- [ ] 所有资源有配对释放（malloc/free, fopen/fclose）
- [ ] 字符串操作用 safe_strncpy 而非 strcpy
- [ ] 共享变量访问已加锁
- [ ] 函数参数 const 正确

**Python 代码：**
- [ ] 无 `except: pass`
- [ ] 公开 API 有类型注解
- [ ] 无未使用的导入（ruff F401）
- [ ] 无未使用的变量（ruff F841）

**JavaScript 代码：**
- [ ] 用 const/let，不用 var
- [ ] 异步代码用 async/await，不用 .then()
- [ ] 禁止 for-in，用 for-of 或 .forEach

---

## 决策树

### 需要修改协议？

```
需要修改协议？
├─ 是 → 检查 PROTOCOL.md 对应章节
│       ├─ 新增消息类型？
│       │   ├─ 是 → 同步修改三处：
│       │   │       1. buildroot-agent/include/agent.h (msg_type_t)
│       │   │       2. buildroot-server/protocol/constants.py (MessageType)
│       │   │       3. PROTOCOL.md (消息定义)
│       │   └─ 否 → 继续
│       └─ 修改现有消息？
│           ├─ 是 → 检查向后兼容性
│           └─ 否 → 开始实现
└─ 否 → 继续
```

### 需要新增功能？

```
新增功能位置？
├─ Agent (C) → 检查 CONSTRAINTS.md 的"运行环境"
│              检查 STYLE.md 的"C代码规范"
├─ Server (Python) → 检查 STYLE.md 的"Python代码规范"
│                    使用 uv 管理依赖
├─ Web (JS/Vue) → 检查 STYLE.md 的"JavaScript代码规范"
└─ 跨组件 → 确保三端协议同步
```

---

## 核心架构速览

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Agent          │   TCP   │   Server        │   WS    │   Web           │
│  (嵌入式设备)    │<──────>│  (中央服务器)    │<──────>│  (管理控制台)   │
│  C语言          │  :8766  │  Python         │  :8765  │  JS/Vue         │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

**运行环境：** buildroot 2015.08.1, gcc 4.9, cmake 2.8.12.2, openssl 1.1.1

---

## 项目目录

```
buildroot-agent/
├── buildroot-agent/     # C Agent (嵌入式设备端)
├── buildroot-server/    # Python Server (中央服务器)
├── buildroot-web/       # Web Console
├── buildroot-web-vue/   # Vue 版本 Web Console
├── scripts/             # 构建/测试脚本
├── postmortem/          # 事后分析文档
├── AGENTS.md            # 本文件
├── ARCHITECTURE.md      # 架构文档
├── STYLE.md             # 代码规范
├── BUILD.md             # 构建命令
├── TESTING.md           # 测试文档
├── CONSTRAINTS.md       # 硬约束
├── PITFALLS.md          # 常见错误
└── PROTOCOL.md          # 通信协议规范
```

---

## 版本管理

- 版本号：`主版本.次版本.修订版本`（如 1.2.3）
- 版本文件：`buildroot-agent/VERSION`
- 修订版本：bug 修复
- 次版本：功能添加
- 主版本：重大变更

---

## 帮助

遇到问题时：
1. 检查 CONSTRAINTS.md（是否违反硬约束）
2. 检查 PITFALLS.md（是否犯了常见错误）
3. 检查 PROTOCOL.md（协议是否正确）
4. 检查 TESTING.md（测试是否覆盖）

不确定时，先问清楚，再动手。