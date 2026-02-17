# Buildroot Agent

嵌入式设备远程管理 Agent

## 安装

### 方式一：解压安装（推荐用于测试）

1. 解压到目标目录：
   ```bash
   tar -xf buildroot-agent-1.1.0.tar
   cd buildroot-agent
   ```

2. 创建配置文件（从示例复制）：
   ```bash
   cp agent.conf.example agent.conf
   vim agent.conf  # 编辑配置
   ```

3. 启动服务：
   ```bash
   ./buildroot-agent -c ./agent.conf -d
   ```

### 方式二：系统安装（推荐用于生产）

```bash
./scripts/install.sh local
```

默认安装到 `/opt/buildroot-agent/`，可通过第二个参数指定安装目录：

```bash
./scripts/install.sh local /custom/path
```

启动服务：
```bash
cd /opt/buildroot-agent
./buildroot-agent -c ./agent.conf -d
```

## 使用

- 直接运行：`./buildroot-agent -c ./agent.conf`
- 后台运行：`./buildroot-agent -c ./agent.conf -d`
- 查看版本：`./buildroot-agent -V`

## 目录结构

```
buildroot-agent/
├── buildroot-agent    # 主程序
├── agent.conf         # 配置文件
├── doc/               # 文档目录
│   ├── LICENSE
│   ├── MANIFEST
│   └── README.md
└── data/              # 运行时数据（启动时创建）
    ├── pid/           # PID 文件
    ├── log/           # 日志文件
    ├── scripts/       # 脚本缓存
    ├── tmp/           # 临时文件
    └── backup/        # 更新备份
```

## 配置

编辑 `agent.conf` 文件修改配置。

主要配置项：
- `server_addr`: 服务器地址
- `device_id`: 设备唯一标识
- `log_path`: 日志目录（默认 `./log`）
- `script_path`: 脚本存放目录（默认 `./scripts`）

## 变更日志

详细的版本变更记录请查看 [CHANGELOG.md](../CHANGELOG.md)。

## 许可证

MIT License
