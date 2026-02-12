#!/bin/bash

# 创建测试更新包的脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGES_DIR="${SCRIPT_DIR}/test_packages"
UPDATES_DIR="${PACKAGES_DIR}/updates"

echo "=== 创建测试更新包 ==="

# 确保目录存在
mkdir -p "${UPDATES_DIR}"

# 版本信息
CURRENT_VERSION="1.0.0"
TEST_VERSIONS=("1.0.1" "1.1.0" "2.0.0" "1.0.1-bad" "1.0.1-corrupted")

# 源二进制文件
SOURCE_BINARY="${PACKAGES_DIR}/buildroot-agent"

if [ ! -f "${SOURCE_BINARY}" ]; then
    echo "错误: 源二进制文件不存在: ${SOURCE_BINARY}"
    exit 1
fi

for version in "${TEST_VERSIONS[@]}"; do
    echo "创建版本 ${version} 的更新包..."
    
    # 创建临时目录
    TEMP_DIR="${PACKAGES_DIR}/temp_${version}"
    PACKAGE_DIR="${TEMP_DIR}/buildroot-agent"
    mkdir -p "${PACKAGE_DIR}"
    
    # 复制二进制文件
    cp "${SOURCE_BINARY}" "${PACKAGE_DIR}/buildroot-agent"
    
    # 创建版本信息文件
    cat > "${PACKAGE_DIR}/VERSION" << EOF
version=${version}
build_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
description=Test update package version ${version}
EOF
    
    # 创建安装脚本
    cat > "${PACKAGE_DIR}/install.sh" << 'EOF'
#!/bin/bash
# Buildroot Agent 安装脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY="${SCRIPT_DIR}/buildroot-agent"

echo "安装 Buildroot Agent..."
echo "版本信息:"
if [ -f "${SCRIPT_DIR}/VERSION" ]; then
    cat "${SCRIPT_DIR}/VERSION"
fi

echo ""
echo "二进制大小: $(stat -c%s "${BINARY}") bytes"
echo "二进制 MD5: $(md5sum "${BINARY}" | cut -d' ' -f1)"

# 设置执行权限
chmod +x "${BINARY}"

echo "安装完成!"
echo "请手动复制 buildroot-agent 到目标位置"
EOF
    
    chmod +x "${PACKAGE_DIR}/install.sh"
    
    # 创建README
    cat > "${PACKAGE_DIR}/README.md" << EOF
# Buildroot Agent 更新包

版本: ${version}
构建时间: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

## 文件说明
- \`buildroot-agent\`: 主要可执行文件
- \`VERSION\`: 版本信息文件
- \`install.sh\`: 安装脚本
- \`README.md\`: 说明文档

## 校验和
\`\`\`
MD5: $(md5sum "${PACKAGE_DIR}/buildroot-agent" | cut -d' ' -f1)
SHA256: $(sha256sum "${PACKAGE_DIR}/buildroot-agent" | cut -d' ' -f1)
\`\`\`
EOF
    
    # 处理特殊版本
    case "${version}" in
        *-bad)
            echo "创建错误版本的包: ${version}"
            # 修改二进制文件使其损坏
            echo "corrupted" >> "${PACKAGE_DIR}/buildroot-agent"
            ;;
        *-corrupted)
            echo "创建损坏的包: ${version}"
            # 截断二进制文件
            truncate -s 1024 "${PACKAGE_DIR}/buildroot-agent"
            ;;
    esac
    
    # 创建 tar.gz 包
    PACKAGE_FILE="${UPDATES_DIR}/agent-update-${version}.tar.gz"
    cd "${TEMP_DIR}"
    tar -czf "${PACKAGE_FILE}" buildroot-agent/
    cd "${SCRIPT_DIR}"
    
    # 生成校验和文件
    cd "${UPDATES_DIR}"
    md5sum "agent-update-${version}.tar.gz" > "agent-update-${version}.tar.gz.md5"
    sha256sum "agent-update-${version}.tar.gz" > "agent-update-${version}.tar.gz.sha256"
    cd "${SCRIPT_DIR}"
    
    # 清理临时目录
    rm -rf "${TEMP_DIR}"
    
    echo "✓ 创建完成: ${PACKAGE_FILE}"
    
    # 显示包信息
    echo "  文件大小: $(stat -c%s "${PACKAGE_FILE}") bytes"
    echo "  MD5: $(cat "${UPDATES_DIR}/agent-update-${version}.tar.gz.md5" | cut -d' ' -f1)"
    echo ""
done

echo "=== 创建测试元数据 ==="

# 创建更新元数据文件
cat > "${UPDATES_DIR}/updates.json" << EOF
{
  "channels": {
    "stable": {
      "latest_version": "1.1.0",
      "versions": {
        "1.0.0": {
          "version": "1.0.0",
          "release_date": "$(date -u -d '7 days ago' '+%Y-%m-%dT%H:%M:%SZ')",
          "file": "agent-update-1.0.0.tar.gz",
          "size": $(stat -c%s "${UPDATES_DIR}/agent-update-1.0.0.tar.gz" 2>/dev/null || echo "0"),
          "md5": "$(cat "${UPDATES_DIR}/agent-update-1.0.0.tar.gz.md5" 2>/dev/null | cut -d' ' -f1 || echo "")",
          "sha256": "$(cat "${UPDATES_DIR}/agent-update-1.0.0.tar.gz.sha256" 2>/dev/null | cut -d' ' -f1 || echo "")",
          "mandatory": false,
          "description": "初始版本",
          "changes": ["初始发布"]
        },
        "1.0.1": {
          "version": "1.0.1",
          "release_date": "$(date -u -d '3 days ago' '+%Y-%m-%dT%H:%M:%SZ')",
          "file": "agent-update-1.0.1.tar.gz",
          "size": $(stat -c%s "${UPDATES_DIR}/agent-update-1.0.1.tar.gz" 2>/dev/null || echo "0"),
          "md5": "$(cat "${UPDATES_DIR}/agent-update-1.0.1.tar.gz.md5" 2>/dev/null | cut -d' ' -f1 || echo "")",
          "sha256": "$(cat "${UPDATES_DIR}/agent-update-1.0.1.tar.gz.sha256" 2>/dev/null | cut -d' ' -f1 || echo "")",
          "mandatory": false,
          "description": "修复版本",
          "changes": ["修复内存泄漏", "改进日志输出"]
        },
        "1.1.0": {
          "version": "1.1.0",
          "release_date": "$(date -u -d '1 day ago' '+%Y-%m-%dT%H:%M:%SZ')",
          "file": "agent-update-1.1.0.tar.gz",
          "size": $(stat -c%s "${UPDATES_DIR}/agent-update-1.1.0.tar.gz" 2>/dev/null || echo "0"),
          "md5": "$(cat "${UPDATES_DIR}/agent-update-1.1.0.tar.gz.md5" 2>/dev/null | cut -d' ' -f1 || echo "")",
          "sha256": "$(cat "${UPDATES_DIR}/agent-update-1.1.0.tar.gz.sha256" 2>/dev/null | cut -d' ' -f1 || echo "")",
          "mandatory": false,
          "description": "功能增强版本",
          "changes": ["新增文件传输功能", "优化网络性能", "改进错误处理"]
        },
        "2.0.0": {
          "version": "2.0.0",
          "release_date": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
          "file": "agent-update-2.0.0.tar.gz",
          "size": $(stat -c%s "${UPDATES_DIR}/agent-update-2.0.0.tar.gz" 2>/dev/null || echo "0"),
          "md5": "$(cat "${UPDATES_DIR}/agent-update-2.0.0.tar.gz.md5" 2>/dev/null | cut -d' ' -f1 || echo "")",
          "sha256": "$(cat "${UPDATES_DIR}/agent-update-2.0.0.tar.gz.sha256" 2>/dev/null | cut -d' ' -f1 || echo "")",
          "mandatory": true,
          "description": "重大版本更新",
          "changes": ["重构通信协议", "新增Web管理界面", "支持批量操作"]
        }
      }
    },
    "beta": {
      "latest_version": "2.0.0",
      "description": "Beta渠道包含最新功能但可能不稳定"
    },
    "dev": {
      "latest_version": "2.0.0-dev",
      "description": "开发渠道，包含最新的开发代码"
    }
  },
  "current_default": "stable",
  "update_policy": {
    "auto_update_enabled": true,
    "require_confirmation": true,
    "backup_enabled": true,
    "rollback_enabled": true,
    "checksum_verification": true
  }
}
EOF

echo "=== 创建测试包清单 ==="

# 创建包清单
cat > "${UPDATES_DIR}/packages.txt" << EOF
# Buildroot Agent 更新包清单
# 生成时间: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

$(for pkg in "${UPDATES_DIR}"/agent-update-*.tar.gz; do
    basename "$pkg" | sed 's/agent-update-\(.*\)\.tar\.gz/\1/'
done | sort -V)

## 包说明:
# 1.0.0      - 当前版本 (基准版本)
# 1.0.1      - 补丁版本 (正常更新测试)
# 1.0.1-bad  - 错误版本 (错误处理测试)  
# 1.0.1-corrupted - 损坏版本 (校验测试)
# 1.1.0      - 功能版本 (功能测试)
# 2.0.0      - 重大版本 (强制更新测试)
EOF

echo "=== 完成 ==="
echo "测试更新包已创建在: ${UPDATES_DIR}"
echo ""
echo "可用的测试包:"
ls -la "${UPDATES_DIR}"/*.tar.gz | awk '{print "  " $9 " (" $5 " bytes)"}'