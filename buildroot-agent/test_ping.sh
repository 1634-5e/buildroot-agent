#!/bin/bash

echo "======================================"
echo "Buildroot Agent Ping监控测试"
echo "======================================"

# 检查agent是否编译成功
if [ ! -f build/bin/buildroot-agent ]; then
    echo "❌ Agent未编译，请先运行编译"
    exit 1
fi

echo "✅ Agent已编译"

# 检查配置文件
if [ -f scripts/ping.conf ]; then
    echo "✅ Ping配置文件存在"
    echo ""
    echo "配置内容："
    cat scripts/ping.conf
else
    echo "⚠️  Ping配置文件不存在，创建默认配置..."
    mkdir -p scripts
    cat > scripts/ping.conf <<'CONF'
# Ping监控配置
enable=true
interval=60
timeout=5
count=4

# Ping目标列表
target=127.0.0.1,本地回环
target=8.8.8.8,Google DNS
CONF
    echo "✅ 已创建默认配置"
fi

echo ""
echo "======================================"
echo "测试步骤："
echo "======================================"
echo ""
echo "1. 启动Server (在另一个终端):"
echo "   cd buildroot-server && python main.py"
echo ""
echo "2. 打开Web控制台:"
echo "   在浏览器中打开 buildroot-web/index.html"
echo ""
echo "3. 启动Agent:"
echo "   cd buildroot-agent && ./build/bin/buildroot-agent"
echo ""
echo "4. 等待约1分钟后，Web端将显示ping结果"
echo ""
echo "======================================"
