#!/bin/sh
cd "$(dirname "$0")/.."
MODE="${1:-local}"
./scripts/build.sh "$MODE"
DESTDIR="${2:-/opt/buildroot-agent}"
cmake --install build --prefix "$DESTDIR"

# 安装后提示
echo ""
echo "========================================="
echo "  安装完成！"
echo "========================================="
echo "安装目录: $DESTDIR"
echo ""
if [ ! -f "$DESTDIR/agent.conf" ]; then
    echo "提示：配置文件尚未创建"
    echo "  请复制示例配置："
    echo "    cd $DESTDIR"
    echo "    cp agent.conf.example agent.conf"
    echo "    # 然后编辑 agent.conf 修改配置"
else
    echo "配置文件已存在：$DESTDIR/agent.conf"
fi
echo ""
echo "启动服务："
echo "  cd $DESTDIR"
echo "  ./buildroot-agent -c ./agent.conf"
echo "========================================="
