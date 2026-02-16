# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2024-02-16
### Added
- 版本号统一管理优化（VERSION 文件）
- 单目录自包含安装（/opt/buildroot-agent）
- Electron 风格版本检查（latest.yml + SHA512）
- 自动生成发布包（TAR 格式）
- CHANGELOG.md 版本变更记录

### Changed
- 所有默认路径改为相对路径
- 移除 S99agent 启动脚本

## [1.0.0] - 2024-01-01
### Added
- 初始版本发布
- TCP Socket 通信
- 系统状态采集上报
- 日志文件上传
- 远程脚本执行
- 交互式 Shell (PTY)
