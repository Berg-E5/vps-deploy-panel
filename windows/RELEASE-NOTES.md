# VPS Deploy Panel v1.0.3

## 修复

- 同一 VPS 的任务互斥改为按 SSH 地址和端口执行，重复服务器别名和多面板进程都不能并发修改同一台机器。
- Windows 原生 Codex Worker 现在会复制并加载 `app/config.py`，修复自动启动时缺少配置模块的问题。
- S-UI 安装任务被 HTTPS 升级任务引用时禁止删除，避免产生孤儿依赖和丢失安装日志。
- 补充端点并发、Windows Worker 隔离导入和 S-UI 依赖删除的回归测试。

本版本包含 v1.0.2 的全部修复。

## 下载

- `VPSDeployPanel-1.0.3-Setup.exe`：主安装包，推荐。
- `VPSDeployPanel-1.0.3-Desktop-Setup.exe`：原生桌面窗口版。
- `VPSDeployPanel-1.0.3-portable.zip`：免安装版。
- `SHA256SUMS.txt`：发布资产 SHA-256 校验表。

## 验证

- Ubuntu 与 Windows Python 测试通过。
- 前端 UI、主题、JavaScript 语法和 Windows PowerShell 启动器测试通过。
- Windows 安装包构建、静默安装、卸载和桌面包内容检查通过。
