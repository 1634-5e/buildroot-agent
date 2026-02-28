# Buildroot Web

Web 控制台，用于管理 Agent 设备。

## 项目结构

```
buildroot-web/
├── index.html           # 主页面（引用 src/main.js）
├── package.json         # npm 配置
├── css/
│   └── style.css       # 样式文件
├── src/                # 源代码
│   ├── main.js         # 入口文件
│   ├── config.js       # 配置常量
│   ├── utils.js        # 工具函数
│   ├── websocket.js    # WebSocket 通信
│   ├── terminal.js     # xterm.js 终端
│   └── app.js          # 应用逻辑
└── public/             # 静态资源（字体等）
```

## 使用方法

### 开发模式

```bash
cd buildroot-web
npm install       # 首次安装依赖
npm run dev       # 启动开发服务器（使用 serve）
```

### 构建

项目使用原生 ES 模块，**不需要打包构建**。

```bash
npm run build    # 输出：No build step required
```

### 生产部署

将以下文件部署到 Web 服务器：
- `index.html`
- `css/`
- `src/`
- `public/`
- `node_modules/`

## 依赖

| 包名 | 用途 |
|------|------|
| @xterm/xterm | 终端模拟器 |
| @xterm/addon-fit | 自适应大小插件 |
| @xterm/addon-search | 搜索插件 |
| @xterm/addon-web-links | 链接识别插件 |
| ace-builds | Ace 代码编辑器 |

## 浏览器兼容性

需要支持 ES Modules 的现代浏览器：Chrome 61+、Firefox 60+、Safari 10.1+、Edge 16+

## 注意事项

- 服务器需要正确配置 MIME 类型（`.js` 文件必须是 `application/javascript`）
- 如果部署到子目录，需要调整 `index.html` 中的路径