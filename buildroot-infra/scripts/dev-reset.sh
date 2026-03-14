#!/bin/bash
# Buildroot Agent 开发环境重置脚本
# 警告：此操作会删除所有数据！

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "⚠️  警告: 此操作将删除所有数据！"
echo ""
read -p "确认重置？(yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ 已取消"
    exit 0
fi

echo ""
echo "🔄 重置 Buildroot Agent 开发环境..."

cd "$PROJECT_DIR"

# 停止并删除容器和卷
if docker compose version &> /dev/null; then
    docker compose down -v --remove-orphans
else
    docker-compose down -v --remove-orphans
fi

# 清理数据目录
echo "🗑️  清理数据目录..."
rm -rf "$PROJECT_DIR"/emqx/data/*
rm -rf "$PROJECT_DIR"/emqx/log/*
# 保留证书
# rm -rf "$PROJECT_DIR"/emqx/certs/*

echo ""
echo "✅ 重置完成"
echo ""
echo "💡 运行 dev-up.sh 重新启动环境"