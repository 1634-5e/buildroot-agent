# Buildroot Web

Web 控制台，用于管理 Agent 设备。

## 技术栈

- **框架**: 原生 ES Modules + Vite 5
- **终端**: xterm.js 5.5
- **编辑器**: Ace Editor 1.32
- **构建工具**: Vite 5（开发服务器 + 生产构建）
- **测试**: Vitest

## 快速开始

### 安装依赖

```bash
cd buildroot-web
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:5173

**开发特性：**
- HMR（热模块替换）：修改代码后自动刷新
- 快速启动：利用 ES Modules 实现即时启动
- 源码映射：直接调试源代码

### 生产构建

```bash
npm run build
```

输出到 `dist/` 目录，包含：
- 压缩后的 JavaScript/CSS
- tree-shaking 优化后的代码
- 静态资源

### 预览生产构建

```bash
npm run preview
```

## 项目结构

```
buildroot-web/
├── src/                 # 源代码
│   ├── main.js          # 入口文件
│   ├── app.js           # 应用逻辑
│   ├── terminal.js      # 终端管理
│   ├── websocket.js     # WebSocket 通信
│   ├── utils.js         # 工具函数
│   └── config.js        # 配置常量
├── css/
│   └── style.css        # 全局样式
├── public/              # 静态资源
├── index.html           # HTML 入口
├── vite.config.js       # Vite 配置
└── package.json         # 依赖配置
```

## 开发说明

### 代码风格

- 使用原生 ES Modules（`import/export`）
- 函数使用 snake_case
- 使用 TypeScript 风格的参数传递
- 完整的错误处理

### 调试

打开浏览器开发者工具，可以：
1. 查看 Console 日志（所有模块都有详细日志）
2. 使用 Network 标签查看模块加载情况
3. 使用 Sources 标签调试源代码

## 部署

### 构建产物

运行 `npm run build` 后，`dist/` 目录包含：
- `index.html` - 主页面
- `assets/` - 压缩后的 JS/CSS
- 静态资源

### 部署到 Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /path/to/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

## 测试

```bash
npm test              # 运行测试
npm run test:watch    # 监听模式
npm run test:coverage  # 生成覆盖率报告
```

## 依赖

| 包名 | 用途 |
|------|------|
| @xterm/xterm | 终端模拟器 |
| @xterm/addon-fit | 自适应大小插件 |
| @xterm/addon-search | 搜索插件 |
| @xterm/addon-web-links | 链接识别插件 |
| ace-builds | Ace 代码编辑器 |
| vite | 构建工具 |
| vitest | 测试框架 |

## 版本历史

- **v2.1.0** - 迁移到 Vite 构建工具，优化开发体验
- **v2.0.0** - 模块化重构，从单文件迁移到 ES Modules