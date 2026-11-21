# VPS Deploy Panel v1.0.6

## 修复

- 物流报价系统和音乐解锁工具在系统依赖步骤会显式启用、重启并验证 nginx。
- 修复 nginx 已安装但处于停止状态时，依赖步骤不会启动 nginx，导致后续 Certbot nginx ACME 预检失败的问题。
- 保留安装前 TCP 80/443 空闲检查，以及安装后的 nginx + Certbot authenticator 检查。
- 增加回归测试，覆盖依赖安装顺序和 nginx 启动验证。

本版本包含 v1.0.5 的全部修复。

## 下载

- `VPSDeployPanel-1.0.6-Setup.exe`：主安装包，推荐。
- `VPSDeployPanel-1.0.6-Desktop-Setup.exe`：原生桌面窗口版。
- `VPSDeployPanel-1.0.6-portable.zip`：免安装版。
- `SHA256SUMS.txt`：发布资产 SHA-256 校验表。

## 验证

- 物流报价和音乐解锁 HTTPS 部署模板回归测试通过。
- Ubuntu 与 Windows Python 测试通过。
- Windows 自动更新助手、启动器和 Release 资产选择测试通过。
- Windows 安装包构建、静默安装、卸载和桌面包内容检查通过。
