#!/bin/bash
# Buildroot Agent 开发环境停止脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🛑 停止 Buildroot Agent 开发环境..."

cd "$PROJECT_DIR"

if docker compose version &> /dev/null; then
    docker compose down
else
    docker-compose down
fi

echo ""
echo "✅ 开发环境已停止"
echo ""
echo "💡 提示:"
echo "   - 数据已保留，重新运行 dev-up.sh 即可恢复"
echo "   - 如需清空数据，运行 dev-reset.sh"