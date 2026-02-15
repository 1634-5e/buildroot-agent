#!/bin/sh
cd "$(dirname "$0")/.."

# 解析参数
MODE=""
VERSION=""

while [ $# -gt 0 ]; do
    case "$1" in
        --version=*)
            VERSION="$1"
            shift
            ;;
        --version)
            VERSION="--version $2"
            shift 2
            ;;
        --local|--cross)
            MODE="${1#--}"
            shift
            ;;
        local|cross)
            MODE="$1"
            shift
            ;;
    esac
done

if [ -z "$MODE" ]; then
    MODE="local"
fi

./scripts/build.sh $VERSION "$MODE"
cmake --build build --target release
cmake --build build --target update-package
ls -lh build/bin/buildroot-agent
ls -lh build/buildroot-agent-*.tar
echo ""

# 计算并输出manifest信息
cd build
TAR_FILE=$(ls -1 buildroot-agent-*.tar 2>/dev/null | head -1)
if [ -n "$TAR_FILE" ]; then
    # 验证文件存在
    if [ ! -f "$TAR_FILE" ]; then
        echo "错误: tar文件不存在: $TAR_FILE"
        exit 1
    fi

    # 获取文件大小（跨平台兼容）
    FILE_SIZE=$(stat -c%s "$TAR_FILE" 2>/dev/null || stat -f%z "$TAR_FILE" 2>/dev/null || ls -l "$TAR_FILE" | awk '{print $5}')

    # 计算SHA256
    SHA256=$(sha256sum "$TAR_FILE" | cut -d' ' -f1)

    # 提取架构名称
    ARCH_NAME=$(echo "$TAR_FILE" | sed -E 's/buildroot-agent-([0-9.]+)-(.*)\.tar/\2/')

    # 提取版本号
    VERSION_NUM=$(echo "$TAR_FILE" | sed -E 's/buildroot-agent-([0-9.]+)-.*\.tar/\1/')

    echo "========================================"
    echo "文件信息:"
    echo "========================================"
    echo "  文件名: $TAR_FILE"
    echo "  版本: $VERSION_NUM"
    echo "  架构: $ARCH_NAME"
    echo "  大小: $FILE_SIZE 字节"
    echo "  SHA256: $SHA256"
    echo "========================================"
    echo ""
    echo "Manifest JSON片段 (复制到manifest.json):"
    echo "========================================"
    echo "  \"$ARCH_NAME\": {"
    echo "    \"file\": \"$TAR_FILE\","
    echo "    \"size\": $FILE_SIZE,"
    echo "    \"sha256\": \"$SHA256\","
    echo "    \"mandatory\": false"
    echo "  }"
    echo "========================================"
    echo ""

    # 如果需要，自动复制到updates目录
    UPDATES_DIR="../../buildroot-server/updates"
    if [ -d "$UPDATES_DIR" ]; then
        # 复制文件
        cp "$TAR_FILE" "$UPDATES_DIR/"
        echo "✓ 已复制 $TAR_FILE 到 $UPDATES_DIR"

        # 更新manifest.json
        MANIFEST_FILE="$UPDATES_DIR/manifest.json"
        if [ -f "$MANIFEST_FILE" ]; then
            # 备份现有manifest
            cp "$MANIFEST_FILE" "${MANIFEST_FILE}.bak"

            # 检查是否有jq工具用于更新JSON
            if command -v jq &> /dev/null; then
                # 使用jq更新manifest
                jq --arg ver "$VERSION_NUM" \
                   --arg arch "$ARCH_NAME" \
                   --arg file "$TAR_FILE" \
                   --argjson size "$FILE_SIZE" \
                   --arg sha256 "$SHA256" \
                   '.latest_version = $ver |
                    .architectures[$arch] = {
                        "file": $file,
                        "size": $size,
                        "sha256": $sha256,
                        "mandatory": false
                    }' "$MANIFEST_FILE" > "${MANIFEST_FILE}.tmp" && \
                   mv "${MANIFEST_FILE}.tmp" "$MANIFEST_FILE"
                echo "✓ 已更新 $MANIFEST_FILE"
            else
                echo "⚠️  未找到jq工具，请手动更新manifest.json"
                echo "   或者运行: apt-get install jq / yum install jq"
            fi
        else
            echo "⚠️  manifest.json不存在，请手动创建"
        fi

        echo ""
        echo "更新文件位置: $UPDATES_DIR/$TAR_FILE"
        echo "Manifest文件位置: $UPDATES_DIR/manifest.json"

        # 验证复制的文件
        if [ -f "$UPDATES_DIR/$TAR_FILE" ]; then
            COPIED_SIZE=$(stat -c%s "$UPDATES_DIR/$TAR_FILE" 2>/dev/null || stat -f%z "$UPDATES_DIR/$TAR_FILE" 2>/dev/null)
            COPIED_SHA256=$(sha256sum "$UPDATES_DIR/$TAR_FILE" | cut -d' ' -f1)

            if [ "$FILE_SIZE" = "$COPIED_SIZE" ] && [ "$SHA256" = "$COPIED_SHA256" ]; then
                echo "✓ 文件验证成功（大小和SHA256匹配）"
            else
                echo "⚠️  文件验证失败！"
                echo "   期望大小: $FILE_SIZE, 实际: $COPIED_SIZE"
                echo "   期望SHA256: $SHA256"
                echo "   实际SHA256: $COPIED_SHA256"
            fi
        fi
    fi
fi
cd ..
