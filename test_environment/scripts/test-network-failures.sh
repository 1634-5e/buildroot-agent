#!/bin/bash
# 测试网络故障场景

set -e

echo "=== 测试网络故障场景 ==="

# 测试连接失败
echo "1. 测试服务器连接失败..."
timeout 5 bash -c "</dev/tcp/non-existent-server/8766" 2>/dev/null && echo "连接成功（异常）" || echo "连接失败（正常）"

# 测试下载中断
echo "2. 测试下载中断模拟..."
TEST_FILE="/tmp/test_download.txt"
echo "开始下载..."
timeout 2 bash -c "for i in {1..100}; do echo 'data $i' >> $TEST_FILE; sleep 0.1; done" || echo "下载被中断"
echo "下载文件大小: $(wc -c < $TEST_FILE 2>/dev/null || echo 0)"

# 测试超时
echo "3. 测试连接超时..."
timeout 3 bash -c "</dev/tcp/google.com/80" && echo "连接成功" || echo "连接超时"

# 清理
rm -f "$TEST_FILE"

echo "=== 网络故障测试完成 ==="
