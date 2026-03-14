#!/bin/bash
# Buildroot Agent 开发环境启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 启动 Buildroot Agent 开发环境..."
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未安装 Docker"
    echo "   请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ 错误: Docker 未运行"
    echo "   请启动 Docker Desktop 或 Docker daemon"
    exit 1
fi

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ 错误: 未安装 Docker Compose"
    echo "   请安装 Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# 创建必要的目录
echo "📁 创建数据目录..."
mkdir -p "$PROJECT_DIR"/emqx/{etc,data,log, certs}
mkdir -p "$PROJECT_DIR"/postgres/init
mkdir -p "$PROJECT_DIR"/redis

# 生成自签名证书（如果不存在）
if [ ! -f "$PROJECT_DIR/emqx/certs/server.pem" ]; then
    echo "🔐 生成自签名证书..."
    cd "$PROJECT_DIR/emqx/certs"
    
    # 生成 CA 证书
    openssl genrsa -out ca.key 2048
    openssl req -new -x509 -days 3650 -key ca.key -out ca.pem \
        -subj "/C=CN/ST=Beijing/L=Beijing/O=Buildroot/OU=CA/CN=Buildroot CA"
    
    # 生成服务器证书
    openssl genrsa -out server.key 2048
    openssl req -new -key server.key -out server.csr \
        -subj "/C=CN/ST=Beijing/L=Beijing/O=Buildroot/OU=Server/CN=localhost"
    
    # 签名
    openssl x509 -req -days 3650 -in server.csr -CA ca.pem -CAkey ca.key \
        -CAcreateserial -out server.pem
    
    # 清理临时文件
    rm -f server.csr ca.srl
    
    cd "$PROJECT_DIR"
    echo "✅ 证书生成完成"
fi

# 启动服务
echo ""
echo "🐳 启动 Docker 容器..."
cd "$PROJECT_DIR"

if docker compose version &> /dev/null; then
    docker compose up -d
else
    docker-compose up -d
fi

# 等待服务就绪
echo ""
echo "⏳ 等待服务就绪..."

# 等待 EMQX
echo -n "  EMQX..."
for i in {1..30}; do
    if curl -s http://localhost:18083/api/v5/status > /dev/null 2>&1; then
        echo " ✅"
        break
    fi
    echo -n "."
    sleep 1
done

# 等待 PostgreSQL
echo -n "  PostgreSQL..."
for i in {1..30}; do
    if docker exec buildroot-postgres pg_isready -U buildroot > /dev/null 2>&1; then
        echo " ✅"
        break
    fi
    echo -n "."
    sleep 1
done

# 等待 Redis
echo -n "  Redis..."
for i in {1..30}; do
    if docker exec buildroot-redis redis-cli -a buildroot123 ping 2>/dev/null | grep -q PONG; then
        echo " ✅"
        break
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 开发环境启动成功！"
echo ""
echo "📊 服务地址:"
echo "   EMQX Dashboard:   http://localhost:18083"
echo "                     用户名: admin"
echo "                     密码: buildroot123"
echo ""
echo "   MQTT Broker:      mqtt://localhost:1883"
echo "   MQTT/TLS:         mqtts://localhost:8883"
echo "   WebSocket:        ws://localhost:8083/mqtt"
echo ""
echo "   PostgreSQL:       localhost:5432"
echo "                     数据库: buildroot_agent"
echo "                     用户名: buildroot"
echo "                     密码: buildroot123"
echo ""
echo "   Redis:            localhost:6379"
echo "                     密码: buildroot123"
echo ""
echo "📝 快速测试:"
echo "   MQTTX 订阅: mqttx sub -h localhost -p 1883 -t 'twin/#' -v"
echo "   MQTTX 发布: mqttx pub -h localhost -p 1883 -t 'twin/test/msg' -m 'hello'"
echo "   WebSocket:  http://localhost:18083 → 工具 → WebSocket 客户端"
echo "   PSQL 连接: psql -h localhost -U buildroot -d buildroot_agent"
echo "   Redis 连接: redis-cli -h localhost -p 6379 -a buildroot123"
echo ""
echo "🛑 停止环境: ./scripts/dev-down.sh"
echo "🔄 重置数据: ./scripts/dev-reset.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"