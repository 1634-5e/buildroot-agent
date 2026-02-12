# Buildroot Agent 更新测试环境

## 目录结构

```
test_environment/
├── agents/          # Agent二进制和脚本
├── server/          # 服务器文件
├── logs/            # 测试日志
├── temp/            # 临时文件
├── backups/         # 备份文件
├── scripts/         # 测试脚本
└── config/          # 配置文件
```

## 使用方法

### 1. 运行完整测试套件
```bash
cd test_environment
./scripts/run-all-tests.sh
```

### 2. 运行单项测试
```bash
# 更新工作流测试
./scripts/test-update-workflow.sh

# 回滚功能测试
./scripts/test-rollback.sh

# 网络故障测试
./scripts/test-network-failures.sh
```

### 3. 使用模拟Agent
```bash
cd agents
./mock-agent.sh start    # 启动
./mock-agent.sh status    # 状态
./mock-agent.sh version   # 版本
./mock-agent.sh stop     # 停止
```

## 配置文件

- `config/agent-test.conf` - Agent测试配置
- `config/server-test.conf` - 服务器测试配置

## 测试覆盖范围

1. **更新工作流测试** - 完整的更新流程
2. **回滚功能测试** - 更新失败时的回滚
3. **网络故障测试** - 网络异常处理
4. **边界条件测试** - 极端情况处理
5. **性能测试** - 更新速度和资源使用

## 清理测试环境

```bash
# 返回到项目根目录
cd ..
# 删除测试环境
rm -rf test_environment
```
