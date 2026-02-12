#!/bin/bash
# 测试更新工作流

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_ENV_DIR="${SCRIPT_DIR}/.."
AGENT_DIR="${TEST_ENV_DIR}/agents"
LOG_DIR="${TEST_ENV_DIR}/logs"

echo "=== 测试更新工作流 ==="

# 启动模拟Agent
echo "1. 启动模拟Agent..."
cd "${AGENT_DIR}"
./mock-agent.sh start &
AGENT_PID=$!
echo "Agent PID: $AGENT_PID"

# 等待Agent启动
sleep 2

# 测试版本检查
echo "2. 测试版本检查..."
./mock-agent.sh update-check

# 模拟更新过程
echo "3. 模拟更新过程..."
echo "  - 备份当前版本..."
cp mock-agent.sh mock-agent.sh.backup

echo "  - 下载新版本..."
sleep 1

echo "  - 验证更新包..."
echo "  - 安装新版本..."
sed -i 's/CURRENT_VERSION="1.0.0"/CURRENT_VERSION="1.1.0"/' mock-agent.sh

echo "  - 重启Agent..."
kill $AGENT_PID 2>/dev/null || true
sleep 1

./mock-agent.sh start &
NEW_AGENT_PID=$!

# 验证更新
echo "4. 验证更新..."
sleep 2
NEW_VERSION=$(./mock-agent.sh version)
echo "新版本: $NEW_VERSION"

# 清理
echo "5. 清理测试环境..."
kill $NEW_AGENT_PID 2>/dev/null || true

echo "=== 更新工作流测试完成 ==="
