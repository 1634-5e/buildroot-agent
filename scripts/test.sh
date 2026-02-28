#!/bin/bash
# Unified test runner for buildroot-agent project
# 统一测试运行器 - 支持 Server/Agent/Web 三端测试

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 测试配置
REPORT_DIR="$PROJECT_ROOT/test-reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEBUG_MODE=false

# 帮助信息
show_help() {
    cat << EOF
Buildroot Agent 统一测试运行器

用法: ./scripts/test.sh [选项]

选项:
    --server            仅运行 Server 端测试
    --agent             仅运行 Agent 端测试
    --web               仅运行 Web 端测试
    --test <ID>         运行指定测试用例 (如 TC-CONN-001)
    --report            生成 HTML 测试报告
    --debug             调试模式 (保留测试环境不清理)
    --list              列出所有可用测试
    -h, --help          显示此帮助信息

示例:
    ./scripts/test.sh                    # 运行全部测试
    ./scripts/test.sh --server           # 仅运行 Server 端测试
    ./scripts/test.sh --test TC-CONN-003 # 运行指定测试
    ./scripts/test.sh --report           # 生成测试报告

EOF
}

# 列出可用测试
list_tests() {
    echo -e "${BLUE}可用测试用例清单:${NC}"
    echo ""
    echo "连接测试 (TC-CONN-xxx):"
    echo "  TC-CONN-001: Server 启动"
    echo "  TC-CONN-002: Agent 连接"
    echo "  TC-CONN-003: 设备注册"
    echo "  TC-CONN-004: 心跳机制"
    echo "  TC-CONN-005: 自动重连"
    echo "  TC-CONN-007: 多 Agent 连接"
    echo ""
    echo "状态测试 (TC-STATUS-xxx):"
    echo "  TC-STATUS-001: 系统状态上报"
    echo "  TC-STATUS-002: 状态字段完整性"
    echo ""
    echo "PTY 测试 (TC-PTY-xxx):"
    echo "  TC-PTY-001: 创建会话"
    echo "  TC-PTY-002: 数据收发"
    echo "  TC-PTY-003: 窗口调整"
    echo "  TC-PTY-005: 关闭会话"
    echo ""
    echo "文件传输测试 (TC-FILE-xxx):"
    echo "  TC-FILE-001: 文件上传"
    echo "  TC-FILE-002: 文件下载"
    echo "  TC-FILE-004: 文件列表"
    echo ""
    echo "命令执行测试 (TC-CMD-xxx):"
    echo "  TC-CMD-001: 简单命令执行"
    echo "  TC-CMD-002: 错误处理"
    echo ""
    echo "Ping 测试 (TC-PING-xxx):"
    echo "  TC-PING-001: Ping 状态上报"
    echo ""
    echo "更新测试 (TC-UPDATE-xxx):"
    echo "  TC-UPDATE-001: 版本检查"
}

# 打印信息
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# 运行 Server 端测试
run_server_tests() {
    info "运行 Server 端测试..."
    cd "$PROJECT_ROOT/buildroot-server"

    local pytest_args="-v"

    if [ "$GENERATE_REPORT" = true ]; then
        mkdir -p "$REPORT_DIR"
        pytest_args="$pytest_args --html=$REPORT_DIR/server-report-$TIMESTAMP.html --self-contained-html"
    fi

    if [ -n "$SPECIFIC_TEST" ]; then
        # 将 TC-XXX-NNN 转换为 pytest 的 -k 参数
        test_name=$(echo "$SPECIFIC_TEST" | tr '[:upper:]' '[:lower:]' | tr '_' '-')
        pytest_args="$pytest_args -k $test_name"
    fi

    if uv run pytest tests/ $pytest_args; then
        success "Server 端测试通过"
        return 0
    else
        error "Server 端测试失败"
        return 1
    fi
}

# 运行 Agent 端测试
run_agent_tests() {
    info "运行 Agent 端测试..."
    cd "$PROJECT_ROOT/buildroot-agent"

    if [ -f "tests/test_integration.sh" ]; then
        if bash tests/test_integration.sh; then
            success "Agent 端测试通过"
            return 0
        else
            error "Agent 端测试失败"
            return 1
        fi
    else
        warning "Agent 端测试脚本不存在，跳过"
        return 0
    fi
}

# 运行 Web 端测试
run_web_tests() {
    info "运行 Web 端测试..."
    cd "$PROJECT_ROOT/buildroot-web"

    if [ -f "tests/test_static.py" ]; then
        if python -m pytest tests/ -v; then
            success "Web 端测试通过"
            return 0
        else
            error "Web 端测试失败"
            return 1
    fi
    else
        warning "Web 端测试脚本不存在，跳过"
        return 0
    fi
}

# 检查协议同步
check_protocol_sync() {
    info "检查 C/Python 协议同步..."
    cd "$PROJECT_ROOT"

    if python scripts/check_protocol_sync.py; then
        success "协议同步检查通过"
        return 0
    else
        error "协议同步检查失败 - C 和 Python 的消息类型定义不一致"
        return 1
    fi
}

# 清理函数
cleanup() {
    if [ "$DEBUG_MODE" = false ]; then
        info "清理测试环境..."
        # 清理临时文件等
        :
    else
        info "调试模式: 跳过清理"
    fi
}

# 主函数
main() {
    local RUN_SERVER=false
    local RUN_AGENT=false
    local RUN_WEB=false
    local RUN_ALL=true
    SPECIFIC_TEST=""
    GENERATE_REPORT=false

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --server)
                RUN_SERVER=true
                RUN_ALL=false
                shift
                ;;
            --agent)
                RUN_AGENT=true
                RUN_ALL=false
                shift
                ;;
            --web)
                RUN_WEB=true
                RUN_ALL=false
                shift
                ;;
            --test)
                SPECIFIC_TEST="$2"
                RUN_ALL=false
                shift 2
                ;;
            --report)
                GENERATE_REPORT=true
                shift
                ;;
            --debug)
                DEBUG_MODE=true
                shift
                ;;
            --list)
                list_tests
                exit 0
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # 设置 trap 清理
    trap cleanup EXIT

    info "开始运行测试..."
    info "项目根目录: $PROJECT_ROOT"

    local exit_code=0

    # 检查协议同步
    if ! check_protocol_sync; then
        exit_code=1
    fi

    # 运行测试
    if [ "$RUN_ALL" = true ] || [ "$RUN_SERVER" = true ]; then
        if ! run_server_tests; then
            exit_code=1
        fi
    fi

    if [ "$RUN_ALL" = true ] || [ "$RUN_AGENT" = true ]; then
        if ! run_agent_tests; then
            exit_code=1
        fi
    fi

    if [ "$RUN_ALL" = true ] || [ "$RUN_WEB" = true ]; then
        if ! run_web_tests; then
            exit_code=1
        fi
    fi

    # 总结
    echo ""
    if [ $exit_code -eq 0 ]; then
        success "所有测试通过!"
    else
        error "部分测试失败"
    fi

    if [ "$GENERATE_REPORT" = true ]; then
        info "测试报告已生成: $REPORT_DIR/"
    fi

    exit $exit_code
}

# 运行主函数
main "$@"
