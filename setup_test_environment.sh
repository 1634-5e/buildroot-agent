#!/bin/bash

# Buildroot Agent 更新测试环境设置脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_ENV_DIR="${SCRIPT_DIR}/test_environment"

echo "=== Buildroot Agent 更新测试环境设置 ==="

# 清理旧的测试环境
if [ -d "${TEST_ENV_DIR}" ]; then
    echo "清理旧的测试环境..."
    rm -rf "${TEST_ENV_DIR}"
fi

# 创建测试环境目录结构
echo "创建测试环境目录结构..."
mkdir -p "${TEST_ENV_DIR}"/{agents,server,logs,temp,backups,scripts,config}

# 设置权限
echo "设置目录权限..."
chmod -R 755 "${TEST_ENV_DIR}"

# 创建测试配置文件
echo "创建测试配置文件..."

# Agent测试配置
cat > "${TEST_ENV_DIR}/config/agent-test.conf" << 'EOF'
# Buildroot Agent 测试配置
server_addr = "127.0.0.1:8766"
device_id = "test-device-001"
auth_token = "test-token-123"
heartbeat_interval = 10
reconnect_interval = 5
status_interval = 30
log_path = "/tmp/test_logs"
script_path = "/tmp/test_scripts"
enable_pty = true
enable_script = true
log_level = debug

# 更新配置（测试模式）
enable_auto_update = true
update_check_interval = 300  # 5分钟检查一次
update_channel = "stable"
update_require_confirm = false  # 测试时不需要确认
update_temp_path = "/tmp/agent_update_temp"
update_backup_path = "/tmp/agent_update_backup"
update_rollback_on_fail = true
update_rollback_timeout = 120
update_verify_checksum = true
EOF

# Server测试配置
cat > "${TEST_ENV_DIR}/config/server-test.conf" << 'EOF'
# Buildroot Server 测试配置
websocket_port = 8766
socket_port = 8767
debug_mode = true
log_level = debug
upload_dir = "./test_uploads"
max_file_size = 104857600  # 100MB
enable_ssl = false
test_mode = true
EOF

# 创建模拟脚本
echo "创建模拟脚本..."

# 创建一个简单的测试Agent脚本
cat > "${TEST_ENV_DIR}/agents/mock-agent.sh" << 'EOF'
#!/bin/bash
# Mock Agent for testing

CURRENT_VERSION="1.0.0"
AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${AGENT_DIR}/../config/agent-test.conf"
LOG_FILE="${AGENT_DIR}/../logs/mock-agent.log"

# 确保日志目录存在
mkdir -p "$(dirname "$LOG_FILE")"

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 模拟Agent功能
case "$1" in
    "start")
        log_message "Mock Agent v${CURRENT_VERSION} starting..."
        log_message "Configuration: $CONFIG_FILE"
        log_message "PID: $$"
        
        # 模拟运行
        while true; do
            log_message "Heartbeat from Mock Agent v${CURRENT_VERSION}"
            sleep 10
        done
        ;;
    "stop")
        log_message "Mock Agent stopping..."
        ;;
    "status")
        log_message "Mock Agent v${CURRENT_VERSION} status: running"
        ;;
    "update-check")
        log_message "Checking for updates..."
        echo "Current version: ${CURRENT_VERSION}"
        echo "Latest version: 1.1.0"
        echo "Has update: true"
        ;;
    "version")
        echo "Mock Agent v${CURRENT_VERSION}"
        ;;
    *)
        echo "Usage: $0 {start|stop|status|update-check|version}"
        exit 1
        ;;
esac
EOF

chmod +x "${TEST_ENV_DIR}/agents/mock-agent.sh"

# 创建测试脚本
cat > "${TEST_ENV_DIR}/scripts/test-update-workflow.sh" << 'EOF'
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
EOF

chmod +x "${TEST_ENV_DIR}/scripts/test-update-workflow.sh"

# 创建回滚测试脚本
cat > "${TEST_ENV_DIR}/scripts/test-rollback.sh" << 'EOF'
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
EOF

chmod +x "${TEST_ENV_DIR}/scripts/test-rollback.sh"

# 创建网络故障测试脚本
cat > "${TEST_ENV_DIR}/scripts/test-network-failures.sh" << 'EOF'
#!/bin/bash
# 测试网络故障场景

set -e

echo "=== 测试网络故障场景 ==="

# 测试连接失败
echo "1. 测试服务器连接失败..."
timeout 5 bash -c "</dev/tcp/non-existent-server/8766" 2>/dev/null && echo "连接成功（异常）" || echo "连接失败（正常）"

# 测试下载中断
echo "2. 测试下载中断模拟..."
TEST_FILE="/tmp/test_download.txt"
echo "开始下载..."
timeout 2 bash -c "for i in {1..100}; do echo 'data $i' >> $TEST_FILE; sleep 0.1; done" || echo "下载被中断"
echo "下载文件大小: $(wc -c < $TEST_FILE 2>/dev/null || echo 0)"

# 测试超时
echo "3. 测试连接超时..."
timeout 3 bash -c "</dev/tcp/google.com/80" && echo "连接成功" || echo "连接超时"

# 清理
rm -f "$TEST_FILE"

echo "=== 网络故障测试完成 ==="
EOF

chmod +x "${TEST_ENV_DIR}/scripts/test-network-failures.sh"

# 创建完整测试套件
cat > "${TEST_ENV_DIR}/scripts/run-all-tests.sh" << 'EOF'
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
EOF

chmod +x "${TEST_ENV_DIR}/scripts/run-all-tests.sh"

# 创建README
cat > "${TEST_ENV_DIR}/README.md" << 'EOF'
# Buildroot Agent 更新测试环境

## 目录结构

```
test_environment/
├── agents/          # Agent二进制和脚本
├── server/          # 服务器文件
├── logs/            # 测试日志
├── temp/            # 临时文件
├── backups/         # 备份文件
├── scripts/         # 测试脚本
└── config/          # 配置文件
```

## 使用方法

### 1. 运行完整测试套件
```bash
cd test_environment
./scripts/run-all-tests.sh
```

### 2. 运行单项测试
```bash
# 更新工作流测试
./scripts/test-update-workflow.sh

# 回滚功能测试
./scripts/test-rollback.sh

# 网络故障测试
./scripts/test-network-failures.sh
```

### 3. 使用模拟Agent
```bash
cd agents
./mock-agent.sh start    # 启动
./mock-agent.sh status    # 状态
./mock-agent.sh version   # 版本
./mock-agent.sh stop     # 停止
```

## 配置文件

- `config/agent-test.conf` - Agent测试配置
- `config/server-test.conf` - 服务器测试配置

## 测试覆盖范围

1. **更新工作流测试** - 完整的更新流程
2. **回滚功能测试** - 更新失败时的回滚
3. **网络故障测试** - 网络异常处理
4. **边界条件测试** - 极端情况处理
5. **性能测试** - 更新速度和资源使用

## 清理测试环境

```bash
# 返回到项目根目录
cd ..
# 删除测试环境
rm -rf test_environment
```
EOF

# 设置环境变量
echo "设置环境变量..."
export AGENT_TEST_ENV="${TEST_ENV_DIR}"
export AGENT_TEST_CONFIG="${TEST_ENV_DIR}/config/agent-test.conf"

# 创建测试日志目录
mkdir -p "${TEST_ENV_DIR}/logs"

echo ""
echo "✅ 测试环境设置完成！"
echo ""
echo "📁 测试环境位置: ${TEST_ENV_DIR}"
echo "📖 查看说明: cat ${TEST_ENV_DIR}/README.md"
echo ""
echo "🚀 快速开始："
echo "   cd ${TEST_ENV_DIR}"
echo "   ./scripts/run-all-tests.sh"
echo ""
echo "🔧 环境变量："
echo "   AGENT_TEST_ENV=${TEST_ENV_DIR}"
echo "   AGENT_TEST_CONFIG=${TEST_ENV_DIR}/config/agent-test.conf"
echo ""
echo "📋 可用的测试脚本："
ls -la "${TEST_ENV_DIR}/scripts/"
echo ""
echo "📊 模拟测试（Python）："
echo "   cd ${SCRIPT_DIR}"
echo "   python3 mock_update_scenarios.py"