# 快速启动指南

## 方式 1：Vite 开发服务器（推荐）

```bash
cd buildroot-web
npm run dev
```

然后打开浏览器访问 http://localhost:5173

**优点：**
- ✅ HMR（热模块替换）：修改代码后自动刷新
- ✅ 快速启动（<1s）
- ✅ 源码映射：直接调试源代码
- ✅ 自动解析模块，无需 Import Map

**适用场景：** 日常开发

---

## 方式 2：Serve 原生 ES Modules（快速测试）

```bash
cd buildroot-web
npx serve . -p 5173
```

然后打开浏览器访问 http://localhost:5173

**优点：**
- ✅ 零配置，直接运行
- ✅ 可以直接看到模块结构

**缺点：**
- ❌ 无 HMR（需要手动刷新）
- ❌ 无代码优化

**适用场景：** 快速测试、原型验证

---

## 快速启动脚本

```bash
cd buildroot-web
chmod +x start.sh
./start.sh
```

脚本会提示你选择启动方式。

---

## ⚠️ 常见错误

### 错误：`Failed to resolve module specifier "@xterm/xterm"`

**原因：** 直接双击打开了 `index.html` 文件

**解决：** 使用上述任一方式启动服务器，然后通过 URL 访问

---

## 生产构建

```bash
cd buildroot-web
npm run build
npm run preview
```

预览地址：http://localhost:4173

