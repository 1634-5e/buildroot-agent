#!/bin/bash
# 运行所有测试

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_ENV_DIR="${SCRIPT_DIR}/.."

echo "=== Buildroot Agent 更新功能完整测试套件 ==="
echo "测试环境: ${TEST_ENV_DIR}"
echo "开始时间: $(date)"
echo

# 运行各项测试
tests=(
    "test-update-workflow.sh:更新工作流测试"
    "test-rollback.sh:回滚功能测试"
    "test-network-failures.sh:网络故障测试"
)

passed=0
failed=0

for test_info in "${tests[@]}"; do
    IFS=':' read -r script_name description <<< "$test_info"
    echo "运行: $description"
    echo "脚本: $script_name"
    echo "---"
    
    if "${SCRIPT_DIR}/$script_name"; then
        echo "✓ $description - 通过"
        ((passed++))
    else
        echo "✗ $description - 失败"
        ((failed++))
    fi
    
    echo
    echo "========================================"
    echo
done

# 输出测试结果
echo "=== 测试结果汇总 ==="
echo "通过: $passed"
echo "失败: $failed"
echo "总计: $((passed + failed))"
echo "成功率: $(( passed * 100 / (passed + failed) ))%"
echo "完成时间: $(date)"

if [ $failed -eq 0 ]; then
    echo "🎉 所有测试通过！"
    exit 0
else
    echo "❌ 有测试失败，请检查日志"
    exit 1
fi
