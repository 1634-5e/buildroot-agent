#!/bin/sh
cd "$(dirname "$0")/.."

MODE="${1:-local}"
./scripts/build.sh "$MODE"

DESTDIR="${2:-/opt/buildroot-agent}"

# 创建目录结构
mkdir -p "$DESTDIR"
mkdir -p "$DESTDIR/logs"
mkdir -p "$DESTDIR/scripts"
mkdir -p "$DESTDIR/temp/packages"
mkdir -p "$DESTDIR/temp/scripts"
mkdir -p "$DESTDIR/backup"

# CMake install（安装到 . 目录）
cmake --install build --prefix "$DESTDIR"

# 创建配置文件（如果不存在）
if [ ! -f "$DESTDIR/agent.conf" ]; then
    echo "创建默认配置文件: $DESTDIR/agent.conf"
    cp config/agent.conf.default "$DESTDIR/agent.conf"
fi

echo "安装完成到: $DESTDIR"
echo "二进制文件: $DESTDIR/buildroot-agent"
echo "配置文件: $DESTDIR/agent.conf"
