#!/bin/bash
# 验证manifest.json中的文件大小和SHA256是否与实际文件匹配

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
UPDATES_DIR="$PROJECT_ROOT/buildroot-server/updates"
MANIFEST_FILE="$UPDATES_DIR/manifest.json"

if [ ! -f "$MANIFEST_FILE" ]; then
    echo "错误: manifest.json 不存在于 $MANIFEST_FILE"
    exit 1
fi

echo "========================================"
echo "验证 Manifest 文件"
echo "========================================"
echo "位置: $MANIFEST_FILE"
echo ""

# 使用jq解析manifest（如果没有jq，显示错误）
if ! command -v jq &> /dev/null; then
    echo "错误: 需要安装jq工具"
    echo "  Ubuntu/Debian: sudo apt-get install jq"
    echo "  CentOS/RHEL: sudo yum install jq"
    echo "  macOS: brew install jq"
    exit 1
fi

# 获取manifest中的架构信息
ARCHS=$(jq -r '.architectures | keys[]' "$MANIFEST_FILE")

if [ -z "$ARCHS" ]; then
    echo "警告: manifest中没有架构信息"
    exit 0
fi

TOTAL_ERRORS=0

for ARCH in $ARCHS; do
    echo "--- 架构: $ARCH ---"

    # 从manifest获取信息
    FILE=$(jq -r ".architectures.$ARCH.file" "$MANIFEST_FILE")
    EXPECTED_SIZE=$(jq -r ".architectures.$ARCH.size" "$MANIFEST_FILE")
    EXPECTED_SHA256=$(jq -r ".architectures.$ARCH.sha256" "$MANIFEST_FILE")

    if [ "$FILE" = "null" ] || [ -z "$FILE" ]; then
        echo "  错误: 没有文件名"
        TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
        continue
    fi

    FULL_PATH="$UPDATES_DIR/$FILE"

    if [ ! -f "$FULL_PATH" ]; then
        echo "  错误: 文件不存在: $FULL_PATH"
        TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
        continue
    fi

    # 获取实际文件信息
    ACTUAL_SIZE=$(stat -c%s "$FULL_PATH" 2>/dev/null || stat -f%z "$FULL_PATH" 2>/dev/null)
    ACTUAL_SHA256=$(sha256sum "$FULL_PATH" | cut -d' ' -f1)

    echo "  文件: $FILE"
    echo "  期望大小: $EXPECTED_SIZE 字节"
    echo "  实际大小: $ACTUAL_SIZE 字节"
    echo "  期望SHA256: ${EXPECTED_SHA256:0:16}..."
    echo "  实际SHA256: ${ACTUAL_SHA256:0:16}..."

    # 验证大小
    if [ "$EXPECTED_SIZE" = "$ACTUAL_SIZE" ]; then
        echo "  ✓ 文件大小匹配"
    else
        echo "  ✗ 文件大小不匹配！"
        TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
    fi

    # 验证SHA256
    if [ "$EXPECTED_SHA256" = "$ACTUAL_SHA256" ]; then
        echo "  ✓ SHA256校验通过"
    else
        echo "  ✗ SHA256校验失败！"
        TOTAL_ERRORS=$((TOTAL_ERRORS + 1))
    fi

    echo ""
done

echo "========================================"
if [ $TOTAL_ERRORS -eq 0 ]; then
    echo "✓ 所有文件验证通过"
    exit 0
else
    echo "✗ 发现 $TOTAL_ERRORS 个错误"
    exit 1
fi
