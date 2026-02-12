#!/bin/bash
# Mock Agent for testing

CURRENT_VERSION="1.1.0"
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
