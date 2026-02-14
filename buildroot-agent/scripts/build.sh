#!/bin/sh
cd "$(dirname "$0")/.."

# 解析参数
VERSION=""
MODE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --version=*)
            VERSION="${1#--version=}"
            shift
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --local)
            MODE="local"
            shift
            ;;
        --cross)
            MODE="cross"
            shift
            ;;
        local)
            MODE="local"
            shift
            ;;
        cross)
            MODE="cross"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--version X.Y.Z] [--local|--cross]"
            exit 1
            ;;
    esac
done

# 如果没有指定 MODE，默认为 local
if [ -z "$MODE" ]; then
    MODE="local"
fi

CMAKE_VERSION=$(cmake --version | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
CMAKE_MAJOR=$(echo "$CMAKE_VERSION" | cut -d. -f1)
CMAKE_MINOR=$(echo "$CMAKE_VERSION" | cut -d. -f2)

if [ "$CMAKE_MAJOR" -eq 2 ] && [ "$CMAKE_MINOR" -le 8 ]; then
    BUILD_DIR="-build build"
else
    BUILD_DIR="-B build"
fi

mkdir -p build

# 构建CMake参数
CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release -DSTATIC_LINK=ON"

if [ -n "$VERSION" ]; then
    CMAKE_ARGS="$CMAKE_ARGS -DAGENT_VERSION=$VERSION"
    echo "Building version: $VERSION"
fi

if [ "$MODE" = "local" ]; then
    ARCH="x86_64"
    echo "Building locally (x86_64, static)"
    cmake $BUILD_DIR $CMAKE_ARGS -DARCH=$ARCH
elif [ "$MODE" = "cross" ]; then
    ARCH="armv7"
    echo "Building cross (armv7, static)"
    CMAKE_ARGS="$CMAKE_ARGS -DCMAKE_TOOLCHAIN_FILE=cmake/arm-buildroot.cmake"
    cmake $BUILD_DIR $CMAKE_ARGS -DARCH=$ARCH
else
    echo "Usage: $0 [--version X.Y.Z] [local|cross]"
    exit 1
fi

cmake --build build
