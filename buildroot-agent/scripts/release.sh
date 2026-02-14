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
echo "Update package ready: build/buildroot-agent-*.tar"
echo "To calculate checksums:"
echo "  cd build"
echo "  md5sum buildroot-agent-*.tar > buildroot-agent-*.tar.md5"
echo "  sha256sum buildroot-agent-*.tar > buildroot-agent-*.tar.sha256"
