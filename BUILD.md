# BUILD.md - 构建命令速查

## 快速参考

| 操作 | 命令 |
|------|------|
| 编译 Agent | `cd buildroot-agent && mkdir -p build && cd build && cmake .. && make` |
| 运行 Server | `cd buildroot-server && uv run python main.py` |
| 运行测试 | `./scripts/test.sh` |
| 代码检查 | `cd buildroot-server && uv run ruff check .` |

---

## C/CMake (buildroot-agent)

### 基本编译

```bash
cd buildroot-agent

# 创建构建目录
mkdir -p build && cd build

# 配置（cmake 2.8.12 不支持 -B 参数）
cmake .. -DCMAKE_BUILD_TYPE=Release -DSTATIC_LINK=ON

# 编译
make

# 输出位置
# bin/buildroot-agent
```

### 构建类型

```bash
# Release 版本（默认）
cmake .. -DCMAKE_BUILD_TYPE=Release

# Debug 版本（包含调试符号）
cmake .. -DCMAKE_BUILD_TYPE=Debug

# 静态链接（嵌入式环境推荐）
cmake .. -DSTATIC_LINK=ON
```

### 交叉编译

```bash
# ARM 交叉编译
cmake .. -DCMAKE_TOOLCHAIN_FILE=cmake/arm-buildroot.cmake
make

# 或使用脚本
./scripts/build.sh --cross
```

### 构建脚本

```bash
# 本地编译（x86_64）
./scripts/build.sh

# 交叉编译（arm）
./scripts/build.sh --cross

# 发布构建 + 打包
./scripts/release.sh
```

### 清理

```bash
# 清理构建
rm -rf buildroot-agent/build

# 完全清理
make clean
```

### 常见问题

**cmake 不支持 -B 参数：**
```bash
# ✗ 错误（cmake 2.8.12 不支持）
cmake -B build

# ✓ 正确
mkdir -p build && cd build && cmake ..
```

**静态链接失败：**
```bash
# 确保安装了静态库
apt-get install libc6-dev  # 或对应的开发包
```

---

## Python (buildroot-server)

### 依赖管理

使用 [uv](https://docs.astral.sh/uv/) 管理 Python 项目。

```bash
cd buildroot-server

# 同步依赖（根据 pyproject.toml）
uv sync

# 添加新依赖
uv add <package>

# 添加开发依赖
uv add --dev <package>

# 移除依赖
uv remove <package>

# 更新 lock 文件
uv lock

# 查看已安装包
uv pip list
```

### 运行服务器

```bash
# 开发模式
uv run python main.py

# 指定配置
uv run python main.py --config config.yaml

# 环境变量
BR_SERVER_HOST=0.0.0.0 uv run python main.py
```

### 代码检查

```bash
# 检查代码问题
uv run ruff check .

# 自动修复
uv run ruff check . --fix

# 格式化
uv run ruff format .

# 检查格式
uv run ruff format --check .

# 类型检查（可选）
uv run mypy .
```

### 环境变量

```bash
# 服务器配置
export BR_SERVER_HOST=0.0.0.0
export BR_SERVER_WS_PORT=8765
export BR_SERVER_TCP_PORT=8766

# 数据库配置
export BR_DATABASE_URL=sqlite:///data/agent.db
```

---

## Web (buildroot-web)

### 静态文件服务

```bash
# 使用 Python 简单服务器
cd buildroot-web
python -m http.server 8080

# 或使用 Node.js
npx serve .
```

### 构建检查

```bash
# 如果有构建步骤
npm run build

# 检查静态文件
python -m pytest tests/test_static.py -v
```

---

## Vue 版本 (buildroot-web-vue)

```bash
cd buildroot-web-vue

# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

---

## 统一测试

```bash
# 运行全部测试
./scripts/test.sh

# 运行特定端测试
./scripts/test.sh --server    # 仅 Server
./scripts/test.sh --agent     # 仅 Agent
./scripts/test.sh --web       # 仅 Web

# 运行特定测试用例
./scripts/test.sh --test TC-CONN-003

# 生成覆盖率报告
./scripts/test.sh --report

# 调试模式（保留测试环境）
./scripts/test.sh --debug
```

---

## 发布流程

### 1. 版本更新

```bash
# 更新版本号
echo "1.2.3" > buildroot-agent/VERSION

# 提交
git add buildroot-agent/VERSION
git commit -m "chore: bump version to 1.2.3"
```

### 2. 构建

```bash
# 编译 Agent
cd buildroot-agent
./scripts/build.sh --cross

# 打包
./scripts/release.sh
```

### 3. 测试

```bash
# 运行完整测试
./scripts/test.sh

# 确保覆盖率 ≥ 40%
```

### 4. 发布

```bash
# 创建标签
git tag v1.2.3
git push origin v1.2.3

# GitHub Release（自动构建）
# 或手动上传 release 包
```

---

## Docker（可选）

```bash
# 构建镜像
docker build -t buildroot-server:latest ./buildroot-server

# 运行容器
docker run -d \
  -p 8765:8765 \
  -p 8766:8766 \
  -e BR_DATABASE_URL=sqlite:///data/agent.db \
  buildroot-server:latest
```

---

## 常见问题

### cmake 找不到

```bash
# Ubuntu/Debian
apt-get install cmake

# macOS
brew install cmake
```

### OpenSSL 缺失

```bash
# Ubuntu/Debian
apt-get install libssl-dev

# macOS
brew install openssl
export OPENSSL_ROOT_DIR=$(brew --prefix openssl)
```

### uv 未安装

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Python 版本不匹配

```bash
# 检查版本
python --version  # 需要 Python 3.10+

# 使用 uv 指定版本
uv python install 3.11
uv python pin 3.11
```

---

## CI/CD 配置

项目使用 GitHub Actions（`.github/workflows/`）：

```yaml
# .github/workflows/test.yml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Test Server
        run: |
          cd buildroot-server
          uv sync
          uv run pytest tests/ -v
```

---

## 环境要求

| 组件 | 版本要求 |
|------|----------|
| cmake | 2.8.12.2+ |
| gcc | 4.9+ |
| Python | 3.10+ |
| uv | 最新版 |
| openssl | 1.1.1+ |

**嵌入式运行环境：**
- buildroot 2015.08.1
- gcc 4.9
- cmake 2.8.12.2
- openssl 1.1.1