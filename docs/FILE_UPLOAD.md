# Buildroot Agent 文件上传功能

## 概述

本文档描述了 Buildroot Agent Web Console 的文件上传功能，该功能专为**极小型设备和弱网环境**设计，支持**流式传输**和**断点续传**。

## 功能特性

### 1. 流式文件上传
- **分片传输**：文件被分割成小块进行传输
- **流式写入**：服务器端使用临时文件 + 随机写入实现真正的流式传输
- **内存友好**：无需将整个文件加载到内存

### 2. 断点续传
- **传输恢复**：网络中断后可以从断点继续上传
- **分片追踪**：服务器记录已接收的分片
- **智能重传**：只传输缺失的分片

### 3. 弱网环境优化

#### 自适应分片大小
```
网络状况        分片大小        适用场景
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
极佳 (>95%)     128 KB         局域网/高速网络
良好            64 KB          普通WiFi/4G
一般 (<60%)     32 KB          慢速WiFi/3G
差              8 KB           极弱网/卫星网络
```

#### 自动重试机制
- 最大重试次数：5次
- 指数退避：1s, 2s, 4s, 8s, 16s
- 失败分片自动重传

#### 传输确认
- 每个分片都需要服务器确认
- 超时机制（30秒）
- 失败自动触发重试

### 4. 文件完整性验证
- **MD5校验**：上传完成后进行完整文件MD5校验
- **大小检查**：验证实际接收大小与声明大小一致
- **分片校验**：可选的分片级校验

## 协议设计

### 新增消息类型

```python
FILE_UPLOAD_START = 0x40      # 开始上传请求
FILE_UPLOAD_DATA = 0x41       # 上传数据分片
FILE_UPLOAD_ACK = 0x42        # 分片确认
FILE_UPLOAD_COMPLETE = 0x43   # 上传完成
FILE_TRANSFER_STATUS = 0x47   # 传输状态/进度
```

### 传输流程

```
客户端                              服务器
  │                                   │
  │  1. FILE_UPLOAD_START           │
  │  {filename, file_size, checksum}│
  │ ──────────────────────────────> │
  │                                   │
  │     FILE_UPLOAD_ACK             │
  │  {transfer_id, chunk_size,      │
  │   total_chunks}                 │
  │ <────────────────────────────── │
  │                                   │
  │  2. FILE_UPLOAD_DATA (循环)     │
  │  {transfer_id, chunk_index,     │
  │   chunk_data}                   │
  │ ──────────────────────────────> │
  │                                   │
  │     FILE_UPLOAD_ACK             │
  │  {transfer_id, chunk_index,     │
  │   success}                      │
  │ <────────────────────────────── │
  │         ...                       │
  │                                   │
  │  3. FILE_UPLOAD_COMPLETE        │
  │  {transfer_id}                  │
  │ ──────────────────────────────> │
  │                                   │
  │     FILE_UPLOAD_COMPLETE        │
  │  {success, filepath}            │
  │ <────────────────────────────── │
```

### 断点续传流程

```
客户端                              服务器
  │                                   │
  │  FILE_UPLOAD_START              │
  │  {..., resume_transfer_id}      │
  │ ──────────────────────────────> │
  │                                   │
  │     FILE_UPLOAD_ACK             │
  │  {resume: true,                 │
  │   received_chunks: [...],       │
  │   missing_chunks: [...]}        │
  │ <────────────────────────────── │
  │                                   │
  │  只传输 missing_chunks          │
```

## 客户端实现 (Web Console)

### 核心类：UploadManager

```javascript
UploadManager
├── init()                    # 初始化
├── startUpload(file)         # 开始上传
├── adaptChunkSize(success)   # 自适应调整分片
├── uploadFile(uploadItem)    # 实际上传
├── calculateMD5(file)        # 计算MD5
├── waitForResponse()         # 等待响应
└── UI更新方法
```

### 使用方式

#### 拖拽上传
```javascript
// 拖拽文件到上传区域
function handleDrop(e) {
    const files = e.dataTransfer.files;
    for (let file of files) {
        UploadManager.startUpload(file);
    }
}
```

#### 文件选择
```javascript
// 点击选择文件
function handleFileSelect(e) {
    const files = e.target.files;
    for (let file of files) {
        UploadManager.startUpload(file);
    }
}
```

### UI 组件

1. **上传区域**
   - 拖拽支持
   - 点击选择文件
   - 视觉反馈

2. **上传队列**
   - 显示待上传文件
   - 上传进度
   - 状态指示

3. **上传统计**
   - 实时速度显示
   - 预计剩余时间
   - 当前分片大小
   - 网络状态

4. **已上传文件列表**
   - 历史记录
   - 文件信息

## 服务器端实现 (Python)

### 核心类：FileTransferManager

```python
FileTransferManager
├── create_upload_session()      # 创建上传会话
├── process_upload_chunk()       # 处理上传分片
├── complete_upload()            # 完成上传
├── get_resume_info()            # 获取断点信息
├── adapt_chunk_size()           # 自适应分片
└── cleanup_expired_sessions()   # 清理过期会话
```

### 文件存储

```
uploads/
├── {transfer_id}_{filename}.tmp    # 临时文件（传输中）
└── {transfer_id}_{filename}        # 最终文件（完成）
```

### 会话管理

- **会话超时**：300秒无活动自动清理
- **定期清理**：每分钟检查过期会话
- **临时文件清理**：会话过期时自动删除

## 弱网优化策略

### 1. 分片大小自适应

```python
def adapt_chunk_size(self, device_id: str, success: bool):
    rates = self.device_success_rates[device_id]
    rates.append(success)
    
    # 保留最近20次记录
    if len(rates) > 20:
        rates.pop(0)
    
    # 根据最近5次成功率调整
    if len(rates) >= 5:
        success_rate = sum(rates[-5:]) / 5
        
        if success_rate < 0.6:
            # 成功率低，减小分片
            chunk_size = max(chunk_size // 2, MIN_CHUNK_SIZE)
        elif success_rate > 0.95:
            # 成功率高，增大分片
            chunk_size = min(chunk_size * 2, MAX_CHUNK_SIZE)
```

### 2. 指数退避重试

```javascript
const delay = RETRY_DELAY_BASE * Math.pow(2, retries - 1);
await sleep(delay);
```

### 3. 超时机制

- **分片传输超时**：30秒
- **会话超时**：300秒
- **连接检测**：WebSocket心跳

## 极小型设备优化

### 内存优化
- 分片大小可调节（最小8KB）
- 流式处理，不缓存整个文件
- 临时文件写入而非内存存储

### CPU优化
- 可选的MD5校验（设备端可关闭）
- 异步处理避免阻塞
- 低优先级后台传输

### 网络优化
- 自适应分片大小
- 批量确认减少往返
- 压缩传输（可选）

## 配置参数

### 服务器端配置

```python
# 分片大小配置
CHUNK_SIZES = {
    'small': 8 * 1024,      # 8KB
    'medium': 32 * 1024,    # 32KB
    'large': 64 * 1024,     # 64KB
    'xlarge': 128 * 1024    # 128KB
}

# 重试配置
MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0  # 秒

# 超时配置
SESSION_TIMEOUT = 300   # 秒

# 存储路径
UPLOAD_DIR = "./uploads"
```

### 客户端配置

```javascript
CHUNK_SIZES: {
    small: 8 * 1024,      // 8KB
    medium: 32 * 1024,    // 32KB
    large: 64 * 1024,     // 64KB
    xlarge: 128 * 1024    // 128KB
},
MAX_RETRIES: 5,
RETRY_DELAY_BASE: 1000,   // ms
```

## 使用示例

### 1. 基本文件上传

```bash
# 启动服务器
python3 examples/server_example.py

# 打开 Web Console
# http://localhost:8765/ (或实际地址)

# 拖拽文件到上传区域
# 或点击上传区域选择文件
```

### 2. 命令行查看上传文件

```bash
# 在服务器交互式控制台中
> uploads

已上传文件 (目录: ./uploads):
--------------------------------------------------------------------------------
文件名                                              大小             修改时间
--------------------------------------------------------------------------------
test.txt                                            1,024 bytes      2024-01-20 10:30:15
firmware.bin                                        2.5 MB           2024-01-20 10:35:22
```

### 3. 断点续传场景

```
1. 开始上传大文件 firmware.bin (100MB)
2. 网络中断在 50% 处
3. 重新拖拽同一文件
4. 系统自动检测并恢复上传
5. 从 50% 继续上传，无需重新开始
```

## 错误处理

### 常见错误及处理

| 错误 | 原因 | 处理 |
|------|------|------|
| 超时 | 网络延迟高 | 自动重试，减小分片 |
| 校验失败 | 数据损坏 | 重传失败分片 |
| 会话过期 | 长时间无活动 | 重新创建上传会话 |
| 存储满 | 磁盘空间不足 | 提示用户清理空间 |
| 文件名非法 | 包含危险字符 | 拒绝上传 |

### 日志记录

```python
# 服务器日志
INFO: [device_001] 创建上传会话: abc123, 文件: test.bin, 大小: 1048576 bytes, 分片: 32, 分片大小: 32768
INFO: [device_001] 接收分片 1/32 (3.1%) - abc123
WARN: [device_001] 网络质量差，减小分片到 16384 bytes
ERROR: [device_001] 分片 5 上传失败 (重试 1/5): 超时
INFO: [device_001] 上传完成: test.bin (1048576 bytes) -> ./uploads/abc123_test.bin
```

## 安全考虑

1. **文件名安全检查**
   - 禁止路径遍历 (`..`, `/`)
   - 禁止隐藏文件 (`.` 开头)
   - 只允许基本文件名

2. **大小限制**
   - 可配置最大文件大小
   - 磁盘空间检查

3. **文件类型限制**（可选）
   - 白名单/黑名单机制
   - MIME类型检查

4. **临时文件清理**
   - 会话过期自动清理
   - 定期扫描残留文件

## 性能指标

### 预期性能

| 网络类型 | 分片大小 | 上传速度 | 断点恢复时间 |
|---------|---------|---------|-------------|
| 局域网   | 128KB   | 10MB/s+ | <1s        |
| 4G      | 64KB    | 1-5MB/s | <3s        |
| 3G      | 32KB    | 100-500KB/s | <5s    |
| 卫星/弱网 | 8KB   | 10-50KB/s | <10s     |

### 资源占用

- **内存**：分片大小的2-3倍
- **CPU**：低（主要在网络IO）
- **磁盘**：文件大小 + 临时文件

## 未来扩展

1. **压缩传输**：对文本文件启用gzip压缩
2. **并行传输**：同时传输多个分片
3. **带宽限制**：可配置的传输速度限制
4. **文件预览**：图片/文本在线预览
5. **云存储集成**：直接上传到S3/OSS

## 故障排除

### 上传失败常见问题

1. **文件太大**
   - 检查服务器磁盘空间
   - 调整分片大小

2. **网络不稳定**
   - 查看网络状态指示
   - 系统自动减小分片

3. **浏览器兼容**
   - 确保支持 FileReader API
   - 检查 WebSocket 连接

4. **服务器无响应**
   - 检查服务器日志
   - 确认 WebSocket 连接正常

## 更新日志

### v1.1.0 - 文件上传功能
- ✨ 新增文件拖拽上传
- ✨ 支持断点续传
- ✨ 自适应分片大小
- ✨ 弱网环境优化
- ✨ 上传进度实时显示
- ✨ 上传速度统计
