# VPS Deploy Panel v1.0.2

## 修复

- 恢复物流报价系统与音乐解锁工具的部署计划生成。
- HTTPS 证书固定使用站点域名，本机模式会正确跳过证书申请。
- 自动更新只接受精确版本的主安装包，并校验 GitHub SHA-256 digest。
- 更新检查与安装接口要求管理员令牌，不再接受任意安装包 URL。
- AI 只读排障关闭 shell、网络、MCP 等工具，并使用临时会话。
- 修改证书域名时会失效待审批的 S-UI 计划。
- 修复 8787 端口被占用后，回退端口无法本机自动登录。
- 修复中文 Windows 下 SSH 输出编码问题。
- 修复 Desktop-Setup/portable 缺少桌面后端入口的问题。
- 主安装包恢复原生 Codex Worker 自动启动所需的依赖和令牌初始化。
- S-UI 部署前检测 TCP 2095/2096；3X-UI 占用订阅端口 2096 时会在计划阶段提前阻断，不再等到远端执行才失败。
- 修复页脚版本与实际客户端版本不一致的问题。
- 任务日志过滤 APT/pip 进度噪声并按完整行截断，避免摘要从半个单词开始。

## 下载

- `VPSDeployPanel-1.0.2-Setup.exe`：主安装包，推荐。
- `VPSDeployPanel-1.0.2-Desktop-Setup.exe`：原生桌面窗口版。
- `VPSDeployPanel-1.0.2-portable.zip`：免安装版。
- `SHA256SUMS.txt`：发布资产 SHA-256 校验表。

## 依赖与验证

- Paramiko 升级到 5.1.0。
- Docker Codex Worker 使用固定版本的 `requirements-codex-worker.txt`。
- Python 测试：Ubuntu 与 Windows 全部通过。
- GitHub Actions：tests 与 windows-installer 均通过。
