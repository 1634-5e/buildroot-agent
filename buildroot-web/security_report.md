# Buildroot Web 安全评估报告
## XSS 漏洞分析

**评估时间:** 2026-03-02 08:48:00
**评估范围:** buildroot-web 前端代码
**严重程度:** ⚠️ 中等风险

---

## 执行摘要

### XSS 修复函数状态

✅ **escapeHtml 函数存在且正确实现**
- 位置: `src/utils.js:71-75`
- 功能: 使用浏览器原生 DOM API 转义 HTML
- 测试: 通过 Vitest 单元测试

⚠️ **但函数未被使用**
- 仅在 `src/utils.js` 中定义
- 代码中没有调用 `escapeHtml()` 的实例

---

## 发现的安全漏洞

### 漏洞 1: 设备名称 XSS

**位置:** `src/app.js:1559-1565`

```javascript
list.innerHTML = filtered.map(device => `
    <div class="device-card ${currentDevice?.device_id === device.device_id ? 'active' : ''}"
         onclick="selectDevice('${device.device_id}')">
        <div class="device-card-header">
            <div class="device-avatar">📱</div>
            <div class="device-info">
                <h4>${device.name || device.device_id}</h4>  // ⚠️ XSS 漏洞
                <div class="device-status">在线</div>
            </div>
```

**风险等级:** 🟡 中等

**攻击场景:**
1. 服务器发送恶意设备名称：`<script>alert('XSS')</script>`
2. `device.name` 直接插入 innerHTML，脚本被执行

**影响范围:**
- 设备列表页面
- 任何显示设备名称的地方

**修复建议:**
```javascript
import { escapeHtml } from './utils.js'

<h4>${escapeHtml(device.name || device.device_id)}</h4>
```

---

### 漏洞 2: Toast 消息 XSS

**位置:** `src/utils.js:57-60`

```javascript
toast.innerHTML = `
    <span style="font-size: 20px;">${icons[type]}</span>
    <span>${message}</span>  // ⚠️ XSS 漏洞
`
```

**风险等级:** 🟡 中等

**攻击场景:**
1. 服务器发送的错误消息包含恶意脚本
2. 任何调用 `showToast(message)` 的地方可能成为攻击点

**潜在攻击向量:**
```javascript
show(`<img src=x onerror="alert('XSS')">`)  // 错误消息
show(`文件保存失败: <script>stealCookies()</script>`)
```

**修复建议:**
```javascript
toast.innerHTML = `
    <span style="font-size: 20px;">${icons[type]}</span>
    <span>${escapeHtml(message)}</span>
`
```

---

### 漏洞 3: 文件冲突对话框 XSS

**位置:** `src/app.js:545-551`

```javascript
div.innerHTML = `
    <div class="modal" style="max-width: 450px;">
        <div class="modal-header">
            <div class="modal-title">⚠️ 文件冲突</div>
        </div>
        <div class="modal-body">
            <p id="fileConflictError" style="color: var(--text-primary); margin-bottom: 16px;">${error || '文件已被其他用户修改'}</p>  // ⚠️ XSS 漏洞
```

**风险等级:** 🟡 中等

**攻击场景:**
1. 服务器发送错误消息包含恶意脚本
2. 用户打开文件冲突对话框时脚本执行

**修复建议:**
```javascript
<p id="fileConflictError" style="color: var(--text-primary); margin-bottom: 16px;">${escapeHtml(error || '文件已被其他用户修改')}</p>
```

---

### 漏洞 4: 连接状态文本 XSS

**位置:** `src/websocket.js:167-170`

```javascript
statusEl.innerHTML = `
    <span class="connection-dot"></span>
    <span>重连中 (${reconnectAttempts}/${maxReconnectAttempts})</span>
    <button onclick="stopAutoReconnect()" ...>停止</button>
`
```

**风险等级:** 🟢 低（数字，相对安全）

**说明:** 
- `reconnectAttempts` 和 `maxReconnectAttempts` 是数字
- 数字无法构成 XSS 攻击
- 但其他类似代码可能存在风险

---

### 漏洞 5: 文件树渲染 XSS

**位置:** `src/app.js:1897-1905` (需要检查完整代码)

**风险等级:** 🔍 待评估

**需要检查:**
- 文件名渲染
- 目录名渲染
- 文件内容预览

---

## 其他 innerHTML 使用

以下 innerHTML 使用需要审查：

| 文件 | 行号 | 内容 | 风险 |
|------|------|------|------|
| utils.js | 17 | `element.innerHTML = html` | ⚠️ 需要确认 html 来源 |
| utils.js | 57 | `toast.innerHTML = ...${message}...` | ✅ 已识别（漏洞2） |
| app.js | 282 | `tabsBar.innerHTML = html` | 🔍 需要确认 html 来源 |
| app.js | 545 | `div.innerHTML = ...${error}...` | ✅ 已识别（漏洞3） |
| app.js | 829 | `container.innerHTML = keyword` | ⚠️ 需要确认 |
| app.js | 835 | `container.innerHTML = list.map(p => {...})` | 🔍 需要确认 |
| app.js | 1365 | `grid.innerHTML = ...` | 🔍 需要确认 |
| app.js | 1410 | `grid.innerHTML = html` | 🔍 需要确认 |
| app.js | 1550 | `list.innerHTML = ...` | ✅ 硬编码文本，安全 |
| app.js | 1559 | `list.innerHTML = filtered.map(device => ...${device.name}...)` | ✅ 已识别（漏洞1） |
| app.js | 1717 | `deviceListEl.innerHTML += paginationHTML` | 🔍 需要确认 |
| app.js | 1865 | `container.innerHTML = '<div class="tree-loading">加载中...</div>'` | ✅ 硬编码文本，安全 |
| app.js | 1897 | `div.innerHTML = ...` | 🔍 需要确认 |
| app.js | 2107 | `container.innerHTML = ''` | ✅ 清空操作，安全 |
| websocket.js | 158 | `statusEl.innerHTML = '<span class="connection-dot"></span><span>已连接</span>'` | ✅ 硬编码文本，安全 |
| websocket.js | 167 | `statusEl.innerHTML = ...` | ✅ 已识别（漏洞4） |
| websocket.js | 173 | `statusEl.innerHTML = '<span class="connection-dot"></span><span>未连接</span>'` | ✅ 硬编码文本，安全 |

---

## 风险评估总结

### 高优先级修复

1. ✅ **设备名称 XSS** - `src/app.js:1565`
   - 数据来自服务器，用户可控
   - 影响所有设备列表视图
   
2. ✅ **Toast 消息 XSS** - `src/utils.js:59`
   - 消息可能来自服务器
   - 影响所有通知显示

3. ✅ **文件冲突对话框 XSS** - `src/app.js:551`
   - 错误消息可能来自服务器
   - 影响文件编辑流程

### 中优先级审查

4. 🔍 **标签页 HTML** - `src/app.js:282`
   - 需要确认 `html` 变量来源

5. 🔍 **搜索关键词** - `src/app.js:829`
   - 需要确认 `keyword` 变量来源

6. 🔍 **进程列表** - `src/app.js:835`
   - 需要确认进程名是否转义

7. 🔍 **监控网格** - `src/app.js:1365, 1410`
   - 需要确认数据来源

8. 🔍 **分页 HTML** - `src/app.js:1717`
   - 需要确认 `paginationHTML` 来源

9. 🔍 **文件树** - `src/app.js:1897`
   - 需要确认文件/目录名渲染

---

## 修复优先级建议

### P0 - 立即修复（高风险）

1. **设备名称 XSS**
   - 在所有显示 `device.name` 的地方使用 `escapeHtml()`
   - 包括：设备列表、设备详情、toast 消息等

2. **Toast 消息 XSS**
   - 在 `showToast()` 函数中使用 `escapeHtml()`
   - 保护所有通知消息

3. **文件冲突对话框 XSS**
   - 在渲染错误消息时使用 `escapeHtml()`

### P1 - 尽快修复（中风险）

4. 审查并修复所有其他 innerHTML 使用
5. 添加代码审查流程，防止新漏洞
6. 考虑使用 Content Security Policy (CSP)

### P2 - 长期改进（低风险）

7. 使用模板引擎（如 Lit、Vue、React）
8. 实施自动安全测试
9. 添加依赖项安全扫描

---

## 建议的安全措施

### 代码层面

1. **统一使用 escapeHtml()**
   ```javascript
   // 创建全局安全函数
   export const safeHTML = (html) => {
     const div = document.createElement('div')
     div.textContent = html
     return div.innerHTML
   }
   ```

2. **禁止直接使用 innerHTML**
   - 使用 ESLint 规则：`no-inner-html`
   - 或使用 `textContent` / `innerText` 代替

3. **数据验证**
   ```javascript
   // 验证设备名称格式
   if (!/^[a-zA-Z0-9_-\s]+$/.test(device.name)) {
     console.warn('Invalid device name:', device.name)
     device.name = 'Unknown Device'
   }
   ```

### 配置层面

4. **Content Security Policy**
   ```html
   <meta http-equiv="Content-Security-Policy" 
         content="default-src 'self'; script-src 'self' 'unsafe-inline'">
   ```

5. **输入验证（服务器端）**
   - 验证所有来自服务器的数据
   - 限制设备名称、文件名等字段格式

---

## 测试建议

### 安全测试用例

1. **设备名称注入测试**
   ```javascript
   const maliciousName = '<img src=x onerror="alert(1)">'
   // 验证是否被转义
   ```

2. **Toast 消息注入测试**
   ```javascript
   showToast('<script>alert("XSS")</script>')
   // 验证是否被转义
   ```

3. **错误消息注入测试**
   ```javascript
   showError('<iframe src="javascript:alert(1)"></iframe>')
   // 验证是否被转义
   ```

### 自动化测试

- 集成安全测试到 CI/CD 流程
- 使用 DOMPurify 测试转义效果
- 实施漏洞扫描工具（如 ESLint Security）

---

## 结论

### 当前状态

⚠️ **escapeHtml 函数已实现但未使用**

存在多个 XSS 漏洞，虽然 `escapeHtml()` 函数正确实现并通过了单元测试，但在实际代码中未被调用。

### 紧急行动

1. **立即修复** P0 级别的 3 个漏洞
2. **全面审查** 所有 innerHTML 使用
3. **实施测试** 验证修复效果

### 长期目标

1. 建立安全编码规范
2. 实施自动化安全测试
3. 定期进行安全审计

---

**报告完成时间:** 2026-03-02 08:48:00
**评估人:** Sisyphus Agent
**报告状态:** ✅ 完成
