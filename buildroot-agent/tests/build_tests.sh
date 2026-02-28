#!/bin/bash
# Agent 端测试构建脚本

cd "$(dirname "$0")/.."

echo "Building Agent tests..."

# 创建构建目录
mkdir -p build
cd build

# 配置 CMake（启用测试）
cmake .. -DENABLE_TESTS=ON -DCMAKE_BUILD_TYPE=Debug

# 构建测试
make test_protocol -j$(nproc) 2>&1 | tail -20

echo ""
echo "Running tests..."
./tests/test_protocol 2>&1 | head -50
