#!/bin/sh
cd "$(dirname "$0")/.."
MODE="${1:-local}"

# 构建和安装
./scripts/build.sh "$MODE"
cmake --build build --target release

# 获取版本号
VERSION=$(cat VERSION)

# 从 CHANGELOG.md 提取指定版本的发布说明
extract_release_notes() {
    local version=$1
    local changelog_file="CHANGELOG.md"

    # 检查 CHANGELOG.md 是否存在
    if [ ! -f "$changelog_file" ]; then
        echo "  - No changelog available for version ${version}"
        return
    fi

    # 提取版本章节内容，并添加缩进
    awk -v ver="$version" '
        BEGIN { in_section = 0; found = 0 }
        /^## \['"$version"'\]/ { in_section = 1; found = 1; next }
        /^## \[/ { if (in_section) exit }
        {
            if (in_section) {
                # 保留缩进，过滤空行
                if (length($0) > 0) {
                    # 为每一行添加 2 个空格缩进，YAML 格式要求
                    print "  " $0
                }
            }
        }
        END { exit (found ? 0 : 1) }
    ' "$changelog_file"
}

# 安装到临时目录（第一阶段）
TEMP_INSTALL=$(pwd)/build/temp-install
rm -rf "$TEMP_INSTALL"
cmake --install build --prefix "$TEMP_INSTALL"

# 创建最终的打包目录结构（不带版本号）
INSTALL_DIR=$(pwd)/build/install-package
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/buildroot-agent"

# 复制文件到打包目录
mv "$TEMP_INSTALL"/buildroot-agent "$INSTALL_DIR/buildroot-agent/"
mv "$TEMP_INSTALL"/agent.conf "$INSTALL_DIR/buildroot-agent/"
mv "$TEMP_INSTALL"/doc "$INSTALL_DIR/buildroot-agent/"

# 清理临时安装目录
rm -rf "$TEMP_INSTALL"

# 生成 tar 包
PACKAGE_NAME="buildroot-agent-${VERSION}.tar"
PACKAGE_PATH=$(pwd)/build/${PACKAGE_NAME}

cd "$INSTALL_DIR"
tar -cf "$PACKAGE_PATH" buildroot-agent
cd - > /dev/null

# 计算校验和
SHA512=$(sha512sum "$PACKAGE_PATH" | cut -d' ' -f1)
SIZE=$(stat -c%s "$PACKAGE_PATH")

# 获取 releaseNotes
RELEASE_NOTES=$(extract_release_notes "$VERSION" 2>/dev/null)
if [ -z "$RELEASE_NOTES" ]; then
    RELEASE_NOTES="  - No release notes available for version ${VERSION}"
fi

# 生成 latest.yml
LATEST_YAML=$(pwd)/build/latest.yml
RELEASE_DATE=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

cat > "$LATEST_YAML" <<EOF
version: $VERSION
files:
  - url: $PACKAGE_NAME
    sha512: $SHA512
    size: $SIZE
path: $PACKAGE_NAME
sha512: $SHA512
releaseDate: $RELEASE_DATE
releaseNotes: |-
$RELEASE_NOTES
EOF

# 输出信息
echo "========================================"
echo "Package: $PACKAGE_NAME"
echo "Size: $SIZE bytes"
echo "SHA512: $SHA512"
echo "========================================"
echo "Generated files:"
ls -lh build/ | grep -E "\.tar$|latest\.yml"
echo "========================================"

# 复制到 server updates 目录
SERVER_UPDATES_DIR=$(cd ../buildroot-server && pwd)/updates
mkdir -p "$SERVER_UPDATES_DIR"
cp "$PACKAGE_PATH" "$LATEST_YAML" "$SERVER_UPDATES_DIR/"
echo "Copied to: $SERVER_UPDATES_DIR/"
echo "========================================"
