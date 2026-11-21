# VPS Deploy Panel v1.0.9

## 修复

- 修复物流报价系统上传大型渠道报价表时出现 `HTTP 413 Request Entity Too Large` 的问题。
- 物流报价系统固定源码切换到包含 `client_max_body_size 64m` 的版本，并更新安装脚本校验值。
- 部署验收新增 nginx 上传上限检查；缺少 64 MB 配置时会直接判定失败，避免“安装成功但无法导入报价表”。
- 保留 v1.0.8 对已有物流报价/音乐解锁安装的保护与状态展示。

本版本包含 v1.0.8 的全部修复。

## 下载

- `VPSDeployPanel-1.0.9-Setup.exe`：主安装包，推荐。
- `VPSDeployPanel-1.0.9-Desktop-Setup.exe`：原生桌面窗口版。
- `VPSDeployPanel-1.0.9-portable.zip`：免安装版。
- `SHA256SUMS.txt`：发布资产 SHA-256 校验表。

## 验证

- 12 MB 级报价表经 Base64 上传时不再触发 nginx 默认 1 MB 限制。
- nginx 配置检查与重新加载通过，后台页面保持 HTTP 200。
- 物流报价固定 commit、安装脚本 SHA-256 和上传上限验收测试通过。
- Ubuntu 与 Windows Python 测试通过。
- Windows 自动更新、启动器和安装包测试通过。
