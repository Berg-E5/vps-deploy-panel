# VPS Deploy Panel

**用网页管理 VPS、部署自己项目的工具。**

添加服务器、核对 SSH 指纹、检查环境、生成部署方案、审批执行 —— 全程在浏览器里完成。

> **当前为 Alpha 测试版**，请先在可以备份或重装的 VPS 上试用。

[在线使用文档](https://berg-e5.github.io/vps-deploy-panel/) · [安装教程](https://berg-e5.github.io/vps-deploy-panel/installation.html) · [常见问题](https://berg-e5.github.io/vps-deploy-panel/troubleshooting.html) · [反馈问题](https://github.com/Berg-E5/vps-deploy-panel/issues)

## 我的项目

| 项目 | 源码 | 部署内容 |
| --- | --- | --- |
| **物流报价系统** | [Berg-E5/logistics-quote](https://github.com/Berg-E5/logistics-quote) | systemd 单元 + nginx 反代 + 可选证书；装完是空站，需后台上传报价表才有价格 |
| **音乐解锁工具** | [Berg-E5/music-unlock](https://github.com/Berg-E5/music-unlock) | 静态文件 + nginx 反代 + 可选证书；解密在浏览器里跑，文件不上传 |

这两个排在首页最前面，部署流程和下面其它项目完全一样 —— 详见 [自建项目：物流报价系统 / 音乐解锁工具](#自建项目物流报价系统--音乐解锁工具)。

## 内置项目

面板还带了一批常用开源项目：3X-UI、S-UI、sing-box、Hysteria2、wg-easy、Dockge Apps、Hiddify Manager。


## 主要功能

- **服务器管理**：添加服务器、SSH 密码/密钥连接、核对主机指纹。
- **向导式部署**：先只读体检环境，确认方案后再执行，过程有进度和日志。
- **HTTPS 证书**：3X-UI、S-UI 可自动申请 IP/域名证书，也可交给 NPM 统一管理 HTTPS。
- **端口管理**：管 VPS 上的 UFW 规则，顺带给出常见云厂商安全组的入口。
- **自定义界面**：多种主题颜色、明暗模式和阅读字号。
- **Codex AI（可选）**：使用自己的 ChatGPT 账号，通过自然语言查询任务、打开面板页面、生成待审批部署方案或分析安装日志，无需另填 API Key。

## 内置项目清单

| 项目 | 当前支持情况 |
| --- | --- |
| **3X-UI** | 自动安装，支持 IP/域名 HTTPS 或 NPM 统一 SSL；NPM 模式可提供公网 HTTP 管理地址 |
| **S-UI** | 自动安装，支持 IP / 域名 HTTPS |
| **sing-box** | 自动安装内核，服务端配置需自行完成 |
| **wg-easy** | Docker Compose 自动部署，需完成首次设置 |
| **[Dockge Apps](https://github.com/slobys/dockge-apps)** | 二开应用中心（NPM、IT-Tools、MyIP）；缺 Docker 可使用官方一键脚本，管理端口随机或自定义；新安装默认公网 IP 直连，执行前需确认风险 |
| **Hysteria2** | 提供部署引导，暂不支持一键安装 |
| **Hiddify Manager** | 专用 Ubuntu VPS 上审批执行官网一键安装（Beta），在任务中打开管理面板完成官方快速设置 |

## 自建项目：物流报价系统 / 音乐解锁工具

这两个是我自己维护的项目，按面板的目录机制接进来，首页排在最前面。

| 项目 | 源码 | 部署内容 |
| --- | --- | --- |
| **物流报价系统** | [Berg-E5/logistics-quote](https://github.com/Berg-E5/logistics-quote) | systemd 单元 + nginx 反代 + 可选 HTTPS 证书 + 首次启动随机 admin 账号 |
| **音乐解锁工具** | [Berg-E5/music-unlock](https://github.com/Berg-E5/music-unlock) | 静态文件 + nginx 反代 + 可选 HTTPS 证书；无常驻服务 |

### 完整部署流程

1. **录入 VPS** —— 填主机地址和 SSH 凭据。面板只保存主机信息，密码不进面板数据库（走系统钥匙串）。
2. **核对 SSH 指纹** —— 面板扫到的指纹必须和云控制台或服务器上**独立算出来的**指纹核对一致，确认后才写进 known_hosts。**软件不会自动信任任何指纹。**
3. **环境预检** —— 只读扫描：系统版本、架构、是否 root、磁盘、systemd、`ss`、80/443 是否被占、目标项目是否已经装过。
4. **生成部署计划** —— 5 步：核对环境 → 装依赖 → 下载固定 commit 并校验 SHA-256 → 执行安装 → 验收。每一步的脚本都能逐条看。
5. **审批执行** —— 审批时**会再跑一次预检**，环境变了当场拦住，不会闷头往下装。
6. **看结果** —— 每一步的输出都在任务日志里。

### 安全底线

- 固定到具体 commit，**不追 main 分支** —— 主分支随时会变，不能直接执行。
- 下载后落盘再校验 `install.sh` 的 SHA-256，**不匹配立刻中止**；不做 `curl | bash` 管道。
- 执行的是仓库里已审阅的 `install.sh`，不是远程一键脚本。
- 端口被占、目标项目已装过 → **直接阻断，不覆盖**。
- nginx 会 `enable` + `restart` 并确认在运行；验收会真的 `curl` 打 80 端口、**带 Host 头走自己的 vhost**，只看 `nginx -t` 不算数。

### 两个项目各自的要点

**物流报价系统**

- 部署目标是 **GitHub 公开源码**，装完是**空站**：没有账号数据、没有报价表。
- 装完进 `/admin`，首次启动随机生成 admin 密码并打印在部署日志里（之后可用 `node server/user.js passwd admin` 重置）。
- 在后台「整表导入」上传报价表 xlsx，约 2～3 分钟生成全部价格，前台立即可用。
- 想要「装完就有数据」就走带数据的发布包安装（`deploy/install-remote.sh`），那条路会带上现有账号和费率。
- 不会覆盖已存在的 `quote-server` 服务；后端端口 8792 被占会自动往后挑，挑好的端口写在 `data/port` 里。

**音乐解锁工具**

- 纯静态站，解密在浏览器 Worker 里跑，**文件不上传服务器**。
- 服务器只放静态文件和 nginx 配置，没有后端、没有数据库、不装常驻服务。

### 已知边界

- 只支持 Debian/Ubuntu 的 root VPS，需要 systemd 和 `ss`。
- 80/443 必须空闲（面板要独占这两个端口做反代和证书签发）。
- 域名要先解析到这台 VPS，否则证书签发会失败 —— 可以先勾「跳过 HTTPS 证书申请」用 HTTP 先验证。
- 面板是 **Alpha**，请先在能备份或重装的 VPS 上试。

### 推回 GitHub

这台开发机直连 `github.com:443` 会被 reset，`git push` 走不通，但 `api.github.com` 是通的。
所以仓库自带了一个走 API 的推送脚本（效果和 `git push` 一样）：

```bash
python scripts/push_github_api.py                      # 推 main
python scripts/push_github_api.py --repo 用户名/仓库名    # 换仓库
python scripts/push_github_api.py --dry-run             # 只看会传什么
```

它上传的是 **git 索引里的原始 blob**（用 `git cat-file` 取），不是工作区文件 ——
Windows 上 `core.autocrlf=true` 时工作区是 CRLF、索引里是 LF，
传工作区文件会让远端存成 CRLF，shell 脚本在 Linux 上会报 `bad interpreter`。

前提是本机装了 `gh` 并登录过（`gh auth login`），token 从 `gh auth token` 取，不落在文件里。


### IPv6 VPS 支持（3X-UI / S-UI）

- 添加服务器时可以填**公网 IPv4 或 IPv6**（例如 `2606:4700:4700::1111`，**不要加方括号**）。连接过程和 IPv4 完全一样：照样核对 SSH 指纹、照样密码或密钥认证、照样要审批才执行。纯 IPv6 和双栈都能用，地址由你自己选。
- **指纹扫不出来的时候**：Windows 的 `Test-NetConnection -ComputerName IPv6 -Port 22` 返回 `TcpTestSucceeded=True` 只说明 TCP 端口开着，不代表 sshd 能正常握手。如果第 2 步扫描失败，在 PowerShell 里跑 `ssh-keyscan -6 -T 15 -p 22 <IPv6>`，把「SSH 协议异常」和「扫描超时」分开看。本面板会区分 Banner、算法协商失败和连接中断，只在未认证阶段的临时 Banner 中断上做有限重试；**扫出来的指纹仍然要你自己去云控制台核对，程序不会替你信任**。
- **3X-UI**：IPv6 上可选本机 SSH 隧道、NPM 反代或面板自动签证书。IP 证书用的是约 160 小时短有效期配置 + 独立的 Certbot 续期；域名证书要求 DNS 的 AAAA 记录指对。签发成功会显示 `https://[IPv6]:端口/路径`（域名证书则显示域名）；NPM 模式仍会明确提示公网明文 HTTP 的风险。
- **S-UI**：IPv6 同样可选本机 SSH 隧道、NPM 或自动签证书。证书签发并校验通过后才开放管理端口 2095；**订阅端口 2096 始终只监听 `127.0.0.1`**。签发失败会尝试恢复本机监听，异常状态不会退化成公网明文。
- **签发前的地址校验**：IPv6 签发前会确认目标地址确实分配给这台 VPS；用域名的话要求它的全部 AAAA 记录指向当前 IPv6。Certbot 走 IPv6 的 TCP 80 做 HTTP-01 挑战，签发后校验证书链、IPv6 TLS 监听和本机公网连接。IP 证书用独立 Certbot 每四小时检查续期，域名用系统 Certbot 定时器。
- **上线前还是要自己验收**：UFW 必须开 IPv6（活跃时改 `/etc/default/ufw` 里的 `IPV6=yes`），云厂商 IPv6 安全组要单独放行 TCP 80 和管理端口并限制来源。本机 curl 通了不等于外网能通。IPv6 的 ACME 流程目前只有模拟测试，**还没在真实 IPv6 VPS + Let's Encrypt 生产环境里跑过**，建议先拿可重装的测试机试。IPv4 流程不受影响。

## Windows 快速开始

### 方式一：安装包（推荐给普通用户）

下载 `VPSDeployPanel-<版本>-Setup.exe` 双击安装即可，**不需要预先装 Python 或 Git**：

- 安装包自带 Python 运行时和全部依赖，装完约 110 MB
- 装到 `%LOCALAPPDATA%\Programs\VPS Deploy Panel`，**不需要管理员权限**
- 开始菜单和桌面都有快捷方式，双击就启动面板并打开浏览器
- 勾选「登录时自动启动」会登记一个计划任务，开机后自动可用
- 面板只监听 `127.0.0.1:8787`，不对外网开放
- 卸载走「设置 → 应用 → VPS Deploy Panel」，会停掉后台进程并移除计划任务

数据、数据库和日志放在 `%LOCALAPPDATA%\VPSDeployPanel`，**不在安装目录里** —— 所以覆盖升级不会丢你的服务器配置和历史任务，重装后直接接着用。

安装包由 `windows/build-installer.ps1` 构建：自带 Python 来自 python-build-standalone，**版本和 SHA-256 都钉死**在脚本里，下载后先校验再解压。

### 方式二：从源码运行（给要改代码的人）

先装 [Git for Windows](https://git-scm.com/downloads/win) 和 [Python 3.12+](https://www.python.org/downloads/windows/)（要带 `py` 启动器）。

打开 **PowerShell**，依次执行：

```powershell
git clone https://github.com/Berg-E5/vps-deploy-panel.git
cd vps-deploy-panel
.\QuickStart-VPSDeployPanel.bat
```

启动后浏览器访问 **http://127.0.0.1:8787**。Windows 本机模式首次启动会自动登录。

**以后启动或更新：** 双击项目文件夹里的 `QuickStart-VPSDeployPanel.bat`。面板已经在跑就直接打开网页；停过之后再双击会先检查更新、备份本地数据，再后台启动。想看终端输出或者用 `Ctrl+C` 停，就单独跑 `Start-VPSDeployPanel.bat`。

> 源码模式下的本机数据在项目目录的 `.env` 和 `data\` 里；安装包模式的数据在 `%LOCALAPPDATA%\VPSDeployPanel`。两者不通用，迁移时直接复制数据库文件即可。

## 用 ChatGPT 订阅接 Codex（可选）

**Windows 默认走原生模式，不用 Docker**：装好 Git 和 Python 就行。跑 `QuickStart-VPSDeployPanel.bat` 后，后台会自己建一个独立的 Python 环境并装官方 Codex SDK —— **不需要装 Docker Desktop、WSL，也不需要装 Codex 桌面版**。首次下载 SDK 的 Windows 运行组件可能要等一会儿，后台「Codex AI」会显示进度。用你自己的 ChatGPT 账号完成一次设备码授权后，之后重启会复用登录状态（登录失效要重新授权）。

旧的 `Enable-Codex-Windows.bat` 入口现在也会走原生启动流程。请用普通 Windows 用户权限启动面板。

原生 Worker 只监听 `127.0.0.1:8789`，工作区、SDK 环境和登录目录都在 `%LOCALAPPDATA%\VPSDeployPanel\codex-native` 下；**不会把面板的 SSH 密码、管理员令牌或数据库路径传给 Worker**。Windows 原生沙箱开了 `prefer_mxc`，只读诊断禁止提权审批 —— 但**同一 Windows 用户下的进程隔离不等于 Docker 或独立用户的强隔离**。请在自己信得过的本机上用，别把后台开到公网。

要关掉自动启动，在本机 `.env` 里加 `VPSDEPLOY_CODEX_AUTO_START=0`；不影响面板其它功能。之前装的 Docker 版 Worker 不会被自动卸载或清数据，但 Windows 默认不再调用它。

**Docker / NAS 启动**：在项目私有 `.env` 里设置至少 24 位随机 `VPSDEPLOY_WORKER_TOKEN`（要和管理员令牌不同），然后跑 `docker compose --profile ai up -d --build`。主程序不会把 SSH 密钥、数据库或 Docker Socket 挂进 AI Worker。

进后台左侧 **Codex AI** → **使用 ChatGPT 账号连接**，浏览器会打开官方验证页，输入一次性设备代码就行。设备码登录要在 ChatGPT 安全设置里开启。授权后可以直接问「最近哪些部署失败了」「给东京那台 VPS 生成一个 S-UI 的方案」。记得用面板里的完整服务器名和项目名 —— 面板会自动做只读体检并把方案打开给你看，你审完再决定要不要执行。自动方案里的 3X-UI、S-UI 和 Dockge Apps 走 SSH 隧道访问；要自定义端口、证书或公网模式，得去部署向导里设。想看具体失败原因，在对应任务里点 **AI 只读排障**。

登录凭据分别存在 Windows 原生 Worker 的专属 `CODEX_HOME`、或 Docker/NAS Worker 的私有 `codex-auth` 卷里，退出登录会清掉授权。面板会把你的指令文字、服务器名称、近期任务状态和项目名称一起发给 Codex；用「AI 只读排障」时还会额外发送脱敏后的日志摘录和基本系统信息。**别在指令、名称或日志里填凭据**。ChatGPT 套餐额度有限，个人登录只能本人用。

## 怎么装一个项目？

1. 点 **添加 VPS**，填服务器地址和 SSH 登录信息。
2. 核对 **SSH 主机指纹**，顺便做一次只读体检。
3. 打开 **项目库**，挑要装的东西。
4. 看安装方案，点头才执行，最后看结果。

Docker / NAS 用户看 [Docker 部署教程](https://berg-e5.github.io/vps-deploy-panel/installation.html#docker)。各项目的具体要求见 [部署文档](https://berg-e5.github.io/vps-deploy-panel/deployments.html)。

## 使用前请注意

- 安装任务要相应的系统权限；部分项目要 Debian / Ubuntu、Docker 或指定端口。
- 本面板默认只给本机访问，**别把管理端口直接开到公网**。
- SSH 主机指纹必须走可信渠道核对；签证书还要有正确的 IP / 域名和防火墙放行。
- 项目还在测试阶段，自动化测试过了不代表所有 VPS 环境都实机验收过。

## 开源协议与致谢

本项目基于 **[slobys/netdeploy-ai](https://github.com/slobys/netdeploy-ai)**（MIT 协议）开发。
原作者的版权声明与许可全文保留在 [LICENSE](LICENSE)。

在这个基础上，本项目做了这些改动：

- 新增 **物流报价系统** 与 **音乐解锁工具** 两个自建项目，排在项目库最前。
- Windows 上没有可用 OpenSSH 客户端时，SSH 执行自动改走 Paramiko 密钥认证；主机密钥仍固定用同一份 known_hosts。
- 安装脚本对 nginx 改为 `enable` + `restart` 并确认在运行，避免「装了但没启动」时站点打不开。
- 验收从「只跑 `nginx -t`」改为「确认 nginx 在跑 + 带 Host 头真实请求自己的 vhost」。
- 安装端口自动挑选并写入 `data/port`，重装时沿用原端口不再漂移。
- 域名校验收紧（连续点、段首段尾横线、单段超 63 字符）。

**开源协议：** [MIT License](LICENSE)

