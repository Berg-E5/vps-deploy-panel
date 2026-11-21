# VPS Deploy Panel v1.0.7

## 修复

- 物流报价系统和音乐解锁工具的 HTTP 验收现在接受跳转到本站 HTTPS 域名的标准 301/302/307/308。
- 拒绝跳转到其他域名或非 HTTPS 地址，避免把错误站点跳转当成成功。
- HTTPS 验收改用 `--connect-to` 连接 VPS 回环地址，同时保留域名 SNI 和可信证书校验。
- 增加物流报价与音乐解锁 HTTPS 验收回归测试。

本版本包含 v1.0.6 的全部修复。

## 下载

- `VPSDeployPanel-1.0.7-Setup.exe`：主安装包，推荐。
- `VPSDeployPanel-1.0.7-Desktop-Setup.exe`：原生桌面窗口版。
- `VPSDeployPanel-1.0.7-portable.zip`：免安装版。
- `SHA256SUMS.txt`：发布资产 SHA-256 校验表。

## 验证

- 物流报价和音乐解锁 HTTPS 验收脚本回归测试通过。
- 公网实测物流报价：HTTP 301 → HTTPS，主页与管理页 HTTP 200，数据接口未登录 401。
- Ubuntu 与 Windows Python 测试通过。
- Windows 自动更新、启动器和安装包测试通过。
