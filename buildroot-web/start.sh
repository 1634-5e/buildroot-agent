#!/bin/bash

# Buildroot Web 快速启动脚本

echo "======================================"
echo "Buildroot Web - 快速启动"
echo "======================================"
echo ""

# 检查是否安装了依赖
if [ ! -d "node_modules" ]; then
    echo "⚠️  node_modules 不存在，正在安装依赖..."
    npm install
    echo ""
fi

echo "请选择启动方式:"
echo "1) 使用 Vite (推荐) - HMR、快速启动"
echo "2) 使用 Serve - 直接运行原生 ES Modules"
echo ""
read -p "请输入选项 (1 或 2): " choice

case $choice in
    1)
        echo ""
        echo "🚀 启动 Vite 开发服务器..."
        echo ""
        npm run dev
        ;;
    2)
        echo ""
        echo "🚀 启动 Serve 服务器..."
        echo ""
        # 首先构建 vite 版本的 importmap 供浏览器使用
        echo "⚠️  注意：Serve 模式需要浏览器支持 Import Map"
        echo "⚠️  推荐使用 Chrome 89+、Firefox 78+、Safari 16.4+"
        echo ""
        npx serve . -p 5173
        ;;
    *)
        echo "❌ 无效选项，默认使用 Vite"
        npm run dev
        ;;
esac
