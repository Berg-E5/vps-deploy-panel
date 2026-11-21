# VPS Deploy Panel v1.0.4

## 修复

- 修复物流报价系统 HTTPS 部署在安装 nginx 后错误要求 TCP 80 空闲的问题。
- 修复音乐解锁工具共用的 HTTPS 预检模板中的相同端口顺序问题。
- HTTPS 预检现在验证 nginx 服务运行和 Certbot nginx authenticator 可用，再交给 nginx 完成 ACME 验证。
- 增加对应回归测试，确保依赖安装与 TLS 预检顺序正确。

本版本包含 v1.0.3 的全部修复。

## 下载

- `VPSDeployPanel-1.0.4-Setup.exe`：主安装包，推荐。
- `VPSDeployPanel-1.0.4-Desktop-Setup.exe`：原生桌面窗口版。
- `VPSDeployPanel-1.0.4-portable.zip`：免安装版。
- `SHA256SUMS.txt`：发布资产 SHA-256 校验表。

## 验证

- Ubuntu 与 Windows Python 测试通过。
- 物流报价和音乐解锁 HTTPS 生成脚本回归测试通过。
- 前端 UI、主题、JavaScript 语法和 Windows PowerShell 启动器测试通过。
- Windows 安装包构建、静默安装、卸载和桌面包内容检查通过。
