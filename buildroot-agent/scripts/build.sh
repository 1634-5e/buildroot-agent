#!/bin/sh
cd "$(dirname "$0")/.."

MODE="${1:-local}"
MODE="${MODE#--}"

CMAKE_VERSION=$(cmake --version | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
CMAKE_MAJOR=$(echo "$CMAKE_VERSION" | cut -d. -f1)
CMAKE_MINOR=$(echo "$CMAKE_VERSION" | cut -d. -f2)

if [ "$CMAKE_MAJOR" -eq 2 ] && [ "$CMAKE_MINOR" -le 8 ]; then
    BUILD_DIR="-build build"
else
    BUILD_DIR="-B build"
fi

mkdir -p build

if [ "$MODE" = "local" ]; then
    echo "Building locally (x86_64, static)"
    cmake $BUILD_DIR -DCMAKE_BUILD_TYPE=Release -DSTATIC_LINK=ON
elif [ "$MODE" = "cross" ]; then
    echo "Building cross (arm, static)"
    cmake $BUILD_DIR -DCMAKE_TOOLCHAIN_FILE=cmake/arm-buildroot.cmake -DCMAKE_BUILD_TYPE=Release -DSTATIC_LINK=ON
else
    echo "Usage: $0 [local|cross]"
    exit 1
fi

cmake --build build
