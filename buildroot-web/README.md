# Buildroot Web Console

Buildroot Agent 的 React 版本 Web 控制台。

## 技术栈

- **框架**: React 18 + TypeScript
- **构建工具**: Vite
- **样式**: Tailwind CSS
- **状态管理**: Zustand
- **终端**: xterm.js
- **图标**: Lucide React

## 开发

### 安装依赖

```bash
npm install
```

### 环境配置

复制 `.env.example` 文件为 `.env` 并根据需要修改默认配置：

```bash
cp .env.example .env
```

`.env` 文件示例：

```bash
# WebSocket 服务器地址（留空自动检测）
VITE_DEFAULT_WS_URL=ws://localhost:8765

# 最大重连次数 (1-50)
VITE_DEFAULT_MAX_RECONNECT=10

# 监控刷新间隔 (1-60 秒)
VITE_DEFAULT_REFRESH_INTERVAL=5

# 自动选择第一个设备
VITE_DEFAULT_AUTO_SELECT=true
```

**注意**: 环境变量仅在构建时读取，修改后需要重新启动开发服务器。

### 启动后端服务器

首先需要启动后端 WebSocket 服务器：

```bash
cd /workspaces/buildroot-agent/buildroot-server
python3 server_example.py
```

服务器将在 `ws://localhost:8765` 启动。

### 启动前端开发服务器

```bash
cd /workspaces/buildroot-agent/buildroot-web
npm run dev
```

访问 http://localhost:3000

> **注意**: 在 GitHub Codespaces 等环境中，前端会自动使用 `wss://` 协议连接到后端。

### 构建

```bash
npm run build
```

构建时会读取当前环境的 `.env` 文件并嵌入到构建产物中。

### 预览构建产物

```bash
npm run preview
```

## 项目结构

```
src/
├── components/
│   ├── Sidebar/           # 侧边栏组件
│   ├── DeviceList/        # 设备列表
│   ├── Terminal/          # 终端 (xterm.js)
│   ├── FileExplorer/      # 文件浏览器
│   ├── Monitor/           # 系统监控
│   ├── ScriptRunner/      # 脚本执行
│   └── Shared/            # 共享组件 (Toast)
├── hooks/
│   └── useWebSocket.ts    # WebSocket 钩子
├── store/
│   └── appStore.ts        # Zustand 状态管理
├── types/
│   └── index.ts           # TypeScript 类型定义
└── utils/
    └── format.ts          # 工具函数
```

## 功能模块

- 设备管理与连接
- 终端会话 (PTY)
- 文件浏览器与编辑
- 系统监控 (CPU/内存/磁盘/网络)
- 进程列表
- 脚本执行

## 配置

### 环境变量配置

通过 `.env` 文件设置默认配置，适用于部署场景：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `VITE_DEFAULT_WS_URL` | 空 | WebSocket 服务器地址，留空自动检测 |
| `VITE_DEFAULT_MAX_RECONNECT` | 10 | 最大重连次数 (1-50) |
| `VITE_DEFAULT_REFRESH_INTERVAL` | 5 | 监控刷新间隔 (1-60 秒) |
| `VITE_DEFAULT_AUTO_SELECT` | true | 自动选择第一个设备 |

### 应用内设置

用户可以通过应用内设置面板覆盖环境变量中的默认值。所有设置会自动保存到浏览器本地存储。

#### 设置选项

- **WebSocket 服务器地址**: 自定义服务器地址
- **认证 Token**: 预留配置项（当前版本未使用）
- **最大重连次数**: 连接失败后的重试次数 (1-50)
- **监控刷新间隔**: 系统监控数据的刷新频率 (1-60 秒)
- **自动选择第一个在线设备**: 连接后自动选中首个设备

#### 输入验证

所有设置项在保存前都会进行验证：

- **WebSocket URL**: 必须使用 `ws://` 或 `wss://` 协议，留空则自动检测
- **认证 Token**: 不能仅为空格字符
- **最大重连次数**: 必须在 1 到 50 之间
- **监控刷新间隔**: 必须在 1 到 60 之间

验证失败时会显示错误提示，并禁用保存按钮。

### WebSocket 连接

**认证说明**: 浏览器端 WebSocket 连接不需要认证 token。认证在服务端处理，前端只需正确连接即可。

**URL 格式**:
- **HTTP 环境**: `ws://hostname:8765`
- **HTTPS 环境**: `wss://hostname:8765`

留空则自动检测当前页面的协议和主机名。

## 部署

### 生产环境配置

1. 修改 `.env` 文件，设置生产环境的默认值：

```bash
VITE_DEFAULT_WS_URL=wss://your-server.com:8765
VITE_DEFAULT_MAX_RECONNECT=10
```

2. 构建生产版本：

```bash
npm run build
```

3. 将 `dist/` 目录部署到静态文件服务器（Nginx、Apache、CDN 等）。

### Nginx 配置示例

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # 前端静态文件
    location / {
        root /path/to/dist;
        try_files $uri $uri/ /index.html;
    }

    # WebSocket 代理（如需）
    location /ws {
        proxy_pass http://localhost:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## 故障排查

### WebSocket 连接问题

**快速诊断**:
- 点击设备列表中的 ⚡ (Activity 图标) 运行连接诊断
- 点击 🔗 图标查看当前 WebSocket URL
- 查看 `WEBSOCKET_FIX.md` 了解修复详情

**常见错误**:

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| WebSocket is closed before connection is established | useEffect 竞态条件 | 已修复，请更新到最新代码 |
| Connection refused | 服务器未运行 | 启动服务器：`python3 server_example.py` |
| ERR_CONNECTION_REFUSED | 端口被阻止 | 检查防火墙和安全组 |
| 无法连接 | URL 错误 | 在设置中修改 WebSocket URL |

**详细排查**:
- `WEBSOCKET_TROUBLESHOOTING.md` - 完整故障排查指南
- `WEBSOCKET_PROTOCOL.md` - 协议说明
- `WEBSOCKET_FIX.md` - 修复总结

## License

MIT
