#!/bin/sh
cd "$(dirname "$0")/.."

MODE="${1:-local}"
MODE="${MODE#--}"

CMAKE_VERSION=$(cmake --version | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
CMAKE_MAJOR=$(echo "$CMAKE_VERSION" | cut -d. -f1)

mkdir -p build

# cmake 2.8.x 不支持 -B 参数，需要手动进入 build 目录
if [ "$CMAKE_MAJOR" -lt 3 ]; then
    cd build
    CMAKE_OPTS=".."
else
    CMAKE_OPTS="-B build"
fi

if [ "$MODE" = "local" ]; then
    echo "Building locally (x86_64, static)"
    cmake $CMAKE_OPTS -DCMAKE_BUILD_TYPE=Release -DSTATIC_LINK=ON
elif [ "$MODE" = "cross" ]; then
    echo "Building cross (arm, static)"
    cmake $CMAKE_OPTS -DCMAKE_TOOLCHAIN_FILE=cmake/arm-buildroot.cmake -DCMAKE_BUILD_TYPE=Release -DSTATIC_LINK=ON
else
    echo "Usage: $0 [local|cross]"
    exit 1
fi

if [ "$CMAKE_MAJOR" -lt 3 ]; then
    cmake --build .
else
    cmake --build build
fi
