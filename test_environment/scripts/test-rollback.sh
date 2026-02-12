#!/bin/bash
# 测试回滚功能

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_ENV_DIR="${SCRIPT_DIR}/.."
AGENT_DIR="${TEST_ENV_DIR}/agents"

echo "=== 测试回滚功能 ==="

# 准备测试环境
echo "1. 准备测试环境..."
cd "${AGENT_DIR}"

# 创建原始版本
cp mock-agent.sh mock-agent-original.sh

# 模拟有问题的更新
echo "2. 模拟有问题的更新..."
sed -i 's/CURRENT_VERSION="1.0.0"/CURRENT_VERSION="1.0.1-corrupted"/' mock-agent.sh
echo "  # 这是有问题的版本" >> mock-agent.sh

# 尝试启动（应该失败）
echo "3. 测试损坏版本启动..."
./mock-agent.sh version || echo "启动失败，符合预期"

# 执行回滚
echo "4. 执行回滚..."
cp mock-agent-original.sh mock-agent.sh

# 验证回滚
echo "5. 验证回滚结果..."
RESTORED_VERSION=$(./mock-agent.sh version)
echo "恢复版本: $RESTORED_VERSION"

# 清理
echo "6. 清理..."
rm -f mock-agent-original.sh mock-agent.sh.backup

echo "=== 回滚测试完成 ==="
