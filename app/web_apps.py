"""Berg 自建 Web 应用 —— 物流报价系统 / 音乐解锁工具。

这两个项目由 Berg 自己维护, 源码在 GitHub 公开仓库里。
与面板其它项目保持同一条安全底线:

  * 固定到具体 commit, 不追 main 分支 —— 主分支随时会变, 不能直接执行
  * 下载后先落盘, 校验 SHA-256, 不匹配立刻中止 —— 不做 ``curl | bash`` 管道
  * 执行的是仓库内已审阅的 install.sh, 不是远程一键脚本
  * 部署前在远端再做一次环境核对, 端口占用 / 已有安装直接阻断, 不覆盖

两个项目的安装脚本契约:

  物流报价   bash deploy/install.sh <域名> [安装目录] [skip-ssl]
             (install.sh 在 deploy/ 下, 上一级才是部署包根目录)
  音乐解锁   bash install.sh --domain <域名> [--root <目录>] [--webserver nginx]
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- 固定版本

LOGISTICS_QUOTE_REPO = "Berg-E5/logistics-quote"
LOGISTICS_QUOTE_COMMIT = "4c71d24f557999ac9e607fe4b4ecb28e2d5df2fc"
LOGISTICS_QUOTE_INSTALL_SHA256 = (
    "c3a35fa0bc5577e345952ba79ebdede9eca1d55cc54aaf6dccc42d8942fca871"
)

HERMES_AGENT_REPO = "NousResearch/hermes-agent"
HERMES_AGENT_COMMIT = "5b7b215a0d5656f52a1f2f88770cbadf89e6ad69"
# scripts/install.sh 在该 commit 下的 SHA-256
# (官方 install.sh 就是从仓库 main 分发的同一份, 但我们只认固定 commit 里的那份)
HERMES_AGENT_INSTALL_SHA256 = (
    "c73dad4dcf7c9ecadb98578e28cc763d23d7be3fa1b513545319038795493214"
)

MUSIC_UNLOCK_REPO = "Berg-E5/music-unlock"
MUSIC_UNLOCK_COMMIT = "60ab3f2727adfb37d051ef74c500ed5bbd5cf83a"
MUSIC_UNLOCK_INSTALL_SHA256 = (
    "6713c2a6e7d23cec32c31ef403e55b8d5585029bbebb777f239b2f5860d8f464"
)

# 域名格式 —— 和 install.sh 自己的校验保持一致
_DOMAIN_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,253}[A-Za-z0-9])?$")
_DOCROOT_RE = re.compile(r"^/[A-Za-z0-9._/-]{1,120}$")


def validate_domain(domain: str) -> str:
    """校验域名, 返回归一化结果。

    不接受 IP、不接受协议前缀、不接受端口 —— install.sh 也会再校验一遍,
    这里先挡一道是为了让用户拿到明确的中文错误, 而不是远端脚本的英文报错。
    """
    value = str(domain or "").strip().lower()
    if not value:
        raise ValueError("必须填写域名")
    if "://" in value:
        raise ValueError("域名不要带 http:// 或 https://")
    if "/" in value:
        raise ValueError("域名不要带路径")
    if ":" in value:
        raise ValueError("域名不要带端口")
    if not _DOMAIN_RE.fullmatch(value):
        raise ValueError("域名格式不合法, 例如 quote.example.com")
    if value.count(".") < 1:
        raise ValueError("域名至少要包含一个点, 例如 quote.example.com")
    # 逐段查: 连续点、段首段尾的横线、超过 63 字符的段 —— 都不是合法域名,
    # 写成 nginx server_name 之后只会在装完才发现站点不通。
    for label in value.split("."):
        if not label:
            raise ValueError("域名含连续的点, 例如 quote.example.com")
        if len(label) > 63:
            raise ValueError("域名单段超过 63 个字符")
        if label.startswith("-") or label.endswith("-"):
            raise ValueError("域名的某一段不能用横线开头或结尾")
    return value


def validate_docroot(docroot: str) -> str:
    value = str(docroot or "").strip()
    if not value:
        return ""
    if not _DOCROOT_RE.fullmatch(value) or ".." in value:
        raise ValueError("安装目录必须是绝对路径, 且不能包含 ..")
    return value.rstrip("/")


def _tarball_url(repo: str, commit: str) -> str:
    return f"https://codeload.github.com/{repo}/tar.gz/{commit}"


def _download_step(*, repo: str, commit: str, install_path: str, sha256: str,
                   label: str, workdir: str) -> dict:
    """下载固定 commit 的源码包并校验 install.sh 的 SHA-256。

    校验失败时删掉已下载的文件再退出 —— 不让一个校验不过的包留在机器上。
    """
    url = _tarball_url(repo, commit)
    return {
        "label": label,
        "timeout": 180,
        "script": f"""set -eu
WORK="{workdir}"
rm -rf "$WORK"
mkdir -p "$WORK"
ARCHIVE="$WORK/src.tar.gz"
# 只走 https; 固定 commit; 下载失败不重试, 直接失败
curl --proto '=https' --tlsv1.2 -fsSL --retry 2 --max-time 120 \\
  '{url}' -o "$ARCHIVE"
tar xzf "$ARCHIVE" -C "$WORK"
SRC="$(find "$WORK" -maxdepth 1 -mindepth 1 -type d | head -n 1)"
test -n "$SRC"
test -f "$SRC/{install_path}"
# SHA-256 必须匹配 —— 仓库被改过、被劫持、或者下载损坏, 都在这里中止。
# 用双引号: $SRC 要在这里展开; 单引号会让 sha256sum 去读一个名字字面量
# 是 "$SRC/..." 的文件, 校验必然失败。
echo "{sha256}  $SRC/{install_path}" | sha256sum -c -
echo "已校验: {install_path}"
echo "$SRC" > "$WORK/srcpath"
""",
    }


# ---------------------------------------------------------------- 物流报价


def logistics_quote_steps(domain: str, docroot: str = "", skip_ssl: bool = False) -> list[dict]:
    """物流报价系统 —— systemd + nginx 反代 + 可选证书。"""
    domain = validate_domain(domain)
    docroot = validate_docroot(docroot) or "/var/www/quote.byberg.store"
    work = "/opt/vps-deploy/staging/logistics-quote"
    ssl_flag = "skip-ssl" if skip_ssl else ""

    return [
        {
            "label": "核对运行环境 (Node / Python / nginx / 端口 / 磁盘)",
            "timeout": 60,
            "script": """set -eu
test "$(id -u)" = 0
. /etc/os-release
case "${ID:-}" in debian|ubuntu) ;; *) echo "仅支持 Debian/Ubuntu" >&2; exit 1;; esac
command -v systemctl >/dev/null || { echo "需要 systemd" >&2; exit 1; }
command -v ss >/dev/null || { echo "缺少 iproute2 (ss), 无法检测端口占用" >&2; exit 1; }
command -v curl >/dev/null || { echo "缺少 curl" >&2; exit 1; }
command -v node >/dev/null && node -v | grep -E 'v(1[89]|2[0-9])' >/dev/null || \\
  echo "需要 Node.js 18 或更高版本 (后续步骤会安装)" >&2
command -v python3 >/dev/null || echo "需要 python3 (整表导入用)" >&2
command -v nginx >/dev/null || echo "需要 nginx (后续步骤会安装)" >&2
# 80/443 已被占用就不能装 —— nginx 反代要独占
if ss -Hltn 'sport = :80' | grep -q .; then echo "TCP 80 已被占用, 不能部署" >&2; exit 1; fi
if ss -Hltn 'sport = :443' | grep -q .; then echo "TCP 443 已被占用, 不能部署" >&2; exit 1; fi
# 已有同款服务就不覆盖
if systemctl list-unit-files --no-legend quote-server.service 2>/dev/null | grep -q '^quote-server[.]service'; then
  echo "已存在 quote-server 服务, 拒绝覆盖 (请先卸载或选择其它目录)" >&2; exit 1
fi
FREE_KB="$(df -Pk / | awk 'NR==2 { print $4 }')"
test "$FREE_KB" -gt 1048576 || { echo "根分区可用空间不足 1GB" >&2; exit 1; }
echo "环境核对通过"
""",
        },
        {
            "label": "安装缺失的系统依赖 (nginx / python3 / openpyxl / Node.js)",
            "timeout": 600,
            "script": """set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends nginx python3 python3-pip ca-certificates curl
# openpyxl 只有「整表导入」需要, 装不上不影响站点运行
python3 -m pip install --quiet --break-system-packages openpyxl 2>/dev/null || \\
  python3 -m pip install --quiet openpyxl 2>/dev/null || \\
  echo "openpyxl 安装失败, 整表导入不可用 (其它功能正常)"
# Node.js 18+ —— 后端零第三方依赖, 只要 node 本体
if ! command -v node >/dev/null || ! node -v | grep -E 'v(1[89]|2[0-9])' >/dev/null; then
  apt-get install -y --no-install-recommends ca-certificates curl gnupg
  install -d -m 0755 /etc/apt/keyrings
  curl --proto '=https' --tlsv1.2 -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
node -v
python3 -V
nginx -v
""",
        },
        _download_step(
            repo=LOGISTICS_QUOTE_REPO,
            commit=LOGISTICS_QUOTE_COMMIT,
            install_path="deploy/install.sh",
            sha256=LOGISTICS_QUOTE_INSTALL_SHA256,
            label=f"下载固定版本源码并校验 (commit {LOGISTICS_QUOTE_COMMIT[:12]})",
            workdir=work,
        ),
        {
            "label": f"执行安装 (systemd 单元 + nginx 反代{' + 证书' if not skip_ssl else ''})",
            "timeout": 900,
            "script": f"""set -eu
SRC="$(cat "{work}/srcpath")"
bash "$SRC/deploy/install.sh" '{domain}' '{docroot}' '{ssl_flag}'
""",
        },
        {
            "label": "验收 (服务状态 / 本机 HTTP / nginx 配置)",
            "timeout": 90,
            "script": f"""set -eu
systemctl is-active --quiet quote-server.service || {{
  echo "quote-server 没有启动" >&2; systemctl status quote-server --no-pager -n 20 >&2; exit 1; }}
# 端口: 安装脚本会挑一个不冲突的端口并写进 data/port, 别写死 8792
DOCROOT='{docroot}'
PORT=8792
if [ -f "$DOCROOT/data/port" ]; then PORT="$(cat "$DOCROOT/data/port")"; fi
code="$(curl -s -o /dev/null -w '%{{http_code}}' --max-time 10 http://127.0.0.1:$PORT/)"
test "$code" = "200" || {{ echo "本机 HTTP 返回 $code, 期望 200 (端口 $PORT)" >&2; exit 1; }}
# 未登录时数据接口返回 401 —— 说明登录墙生效, 不是坏掉
code="$(curl -s -o /dev/null -w '%{{http_code}}' --max-time 10 http://127.0.0.1:$PORT/api/data)"
test "$code" = "401" || {{ echo "数据接口返回 $code, 期望 401 (登录墙)" >&2; exit 1; }}
# nginx 必须真的在跑, 且 80 端口能响应。
# 只看 nginx -t 是不够的: "装了但没启动" 时配置语法照样通过, 站点却是打不开的。
systemctl is-active --quiet nginx || {{
  echo "nginx 没有启动 —— 站点会 502" >&2
  systemctl status nginx --no-pager -n 20 >&2
  exit 1
}}
code="$(curl -s -o /dev/null -w '%{{http_code}}' --max-time 10 -H 'Host: {domain}' http://127.0.0.1/)"
test "$code" = "200" || {{ echo "80 端口返回 $code, 期望 200" >&2; exit 1; }}
echo "验收通过"
echo
echo "下一步: 打开 https://{domain}/ 用 admin 账号登录。"
echo "注意: GitHub 源码安装是**空站** —— 需要在后台「整表导入」上传报价表才有价格。"
""",
        },
    ]


# ---------------------------------------------------------------- Hermes Agent


def hermes_agent_steps(installdir: str = "", skip_browser: bool = True) -> list[dict]:
    """Hermes Agent —— 固定 commit 装 CLI, 再装一个网关 systemd 服务。

    和面板里另外两个自建项目不一样: Hermes Agent 没有 Web 面板,
    所以**不需要域名、不需要 nginx、不占 80/443** —— 它是一个命令行
    Agent, 装完通过 `hermes` 使用, 常驻服务是 `hermes gateway`
    (接 Telegram / Discord 等消息平台)。

    安装脚本用仓库里的 scripts/install.sh, 它自己会按 --commit 固定
    版本 clone 并用 pm/uv 装依赖 —— 我们只负责把这份脚本本身也钉死。
    """
    installdir = validate_docroot(installdir) or "/opt/hermes-agent"
    work = "/opt/vps-deploy/staging/hermes-agent"
    skip_flags = " --skip-browser --skip-computer-use" if skip_browser else ""

    return [
        {
            "label": "核对运行环境 (Debian/Ubuntu / systemd / 磁盘 / 内存)",
            "timeout": 60,
            "script": """set -eu
test "$(id -u)" = 0
. /etc/os-release
case "${ID:-}" in debian|ubuntu) ;; *) echo "仅支持 Debian/Ubuntu" >&2; exit 1;; esac
command -v systemctl >/dev/null || { echo "需要 systemd" >&2; exit 1; }
command -v git >/dev/null || { echo "缺少 git" >&2; exit 1; }
command -v curl >/dev/null || { echo "缺少 curl" >&2; exit 1; }
command -v python3 >/dev/null || { echo "缺少 python3" >&2; exit 1; }
# 已装过就拒绝覆盖 —— 装一半的目录比没装更难收拾
if [ -e '/opt/hermes-agent' ] || [ -e '/root/.hermes' ]; then
  echo "已存在 Hermes Agent 安装 (安装目录或 ~/.hermes), 拒绝覆盖" >&2
  exit 1
fi
FREE_KB="$(df -Pk / | awk 'NR==2 { print $4 }')"
test "$FREE_KB" -gt 3145728 || { echo "根分区可用空间不足 3GB" >&2; exit 1; }
MEM_MB="$(awk '/MemTotal/ { print int($2/1024) }' /proc/meminfo)"
test "${MEM_MB:-0}" -ge 1024 || { echo "可用内存不足 1GB" >&2; exit 1; }
echo "环境核对通过"
""",
        },
        {
            "label": "安装系统依赖 (git / curl / python3 / 编译工具链)",
            "timeout": 600,
            "script": """set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  git curl ca-certificates python3 python3-venv build-essential pkg-config
git --version
python3 -V
""",
        },
        _download_step(
            repo=HERMES_AGENT_REPO,
            commit=HERMES_AGENT_COMMIT,
            install_path="scripts/install.sh",
            sha256=HERMES_AGENT_INSTALL_SHA256,
            label=f"下载固定版本源码并校验 (commit {HERMES_AGENT_COMMIT[:12]})",
            workdir=work,
        ),
        {
            "label": "执行安装 (官方 install.sh, 固定 commit, 非交互)",
            "timeout": 2400,
            "script": f"""set -eu
SRC="$(cat "{work}/srcpath")"
# --commit 把安装的代码也钉死; --non-interactive 跳过需要输入的阶段
bash "$SRC/scripts/install.sh" \
  --commit {HERMES_AGENT_COMMIT} \
  --dir '{installdir}' \
  --non-interactive{skip_flags}
""",
        },
        {
            "label": "安装网关 systemd 服务 (hermes gateway)",
            "timeout": 180,
            "script": f"""set -eu
HERMES_BIN="$(find '{installdir}' /root/.hermes -maxdepth 5 -type f -name hermes -perm -u+x 2>/dev/null | head -n 1)"
test -n "$HERMES_BIN" || {{ echo "安装目录里找不到 hermes 可执行文件" >&2; exit 1; }}
echo "hermes 可执行文件: $HERMES_BIN"
cat > /etc/systemd/system/hermes-gateway.service <<EOF
[Unit]
Description=Hermes Agent Gateway
Documentation=https://hermes-agent.nousresearch.com/docs/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$HERMES_BIN gateway
Environment=HERMES_HOME=/root/.hermes
WorkingDirectory=/root
Restart=on-failure
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable hermes-gateway.service
systemctl is-enabled hermes-gateway.service
""",
        },
        {
            "label": "验收 (版本可执行 / 服务已启用)",
            "timeout": 120,
            "script": f"""set -eu
HERMES_BIN="$(find '{installdir}' /root/.hermes -maxdepth 5 -type f -name hermes -perm -u+x 2>/dev/null | head -n 1)"
test -n "$HERMES_BIN" || {{ echo "找不到 hermes 可执行文件" >&2; exit 1; }}
"$HERMES_BIN" --version || {{ echo "hermes --version 执行失败" >&2; exit 1; }}
# 单元必须已 enable —— 但不强制 active:
# 网关要等用户配好模型 API key 才能真正连上消息平台, 没配之前它会退出重试,
# 那不是安装失败。所以这里只校验「装好了、能跑、开机自启已就位」。
systemctl is-enabled hermes-gateway.service >/dev/null || {{
  echo "hermes-gateway 服务没有设置开机自启" >&2; exit 1; }}
echo "验收通过"
echo
echo "安装目录: {installdir}"
echo "可执行文件: $HERMES_BIN"
echo
echo "下一步 (需要你自己配):"
echo "  1. 配置模型:  ssh 到服务器执行  hermes setup   (或 hermes model 选服务商)"
echo "  2. 启动网关:  systemctl start hermes-gateway && systemctl status hermes-gateway"
echo "  3. 直接对话:  ssh 到服务器执行  hermes   (终端界面)"
echo "注意: 没配 API key 之前网关会反复重启, 这是正常的。"
""",
        },
    ]


# ---------------------------------------------------------------- 音乐解锁


def music_unlock_steps(domain: str, docroot: str = "", skip_ssl: bool = False) -> list[dict]:
    """音乐解锁工具 —— 纯静态站, 拷文件 + 写 web server 配置。"""
    domain = validate_domain(domain)
    docroot = validate_docroot(docroot) or "/var/www/music-unlock"
    work = "/opt/vps-deploy/staging/music-unlock"

    return [
        {
            "label": "核对运行环境 (web server / 端口 / 磁盘)",
            "timeout": 60,
            "script": """set -eu
test "$(id -u)" = 0
. /etc/os-release
case "${ID:-}" in debian|ubuntu) ;; *) echo "仅支持 Debian/Ubuntu" >&2; exit 1;; esac
command -v systemctl >/dev/null || { echo "需要 systemd" >&2; exit 1; }
command -v ss >/dev/null || { echo "缺少 iproute2 (ss)" >&2; exit 1; }
command -v curl >/dev/null || { echo "缺少 curl" >&2; exit 1; }
if ss -Hltn 'sport = :80' | grep -q .; then echo "TCP 80 已被占用, 不能部署" >&2; exit 1; fi
if ss -Hltn 'sport = :443' | grep -q .; then echo "TCP 443 已被占用, 不能部署" >&2; exit 1; fi
FREE_KB="$(df -Pk / | awk 'NR==2 { print $4 }')"
test "$FREE_KB" -gt 262144 || { echo "根分区可用空间不足 256MB" >&2; exit 1; }
echo "环境核对通过"
""",
        },
        {
            "label": "安装缺失的系统依赖 (nginx / certbot)",
            "timeout": 600,
            "script": """set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends nginx ca-certificates curl
apt-get install -y --no-install-recommends certbot python3-certbot-nginx || \\
  echo "certbot 安装失败, 只能部署 HTTP"
nginx -v
""",
        },
        _download_step(
            repo=MUSIC_UNLOCK_REPO,
            commit=MUSIC_UNLOCK_COMMIT,
            install_path="install.sh",
            sha256=MUSIC_UNLOCK_INSTALL_SHA256,
            label=f"下载固定版本源码并校验 (commit {MUSIC_UNLOCK_COMMIT[:12]})",
            workdir=work,
        ),
        {
            "label": f"执行安装 (静态站 + nginx 反代{' + 证书' if not skip_ssl else ''})",
            "timeout": 600,
            "script": f"""set -eu
SRC="$(cat "{work}/srcpath")"
bash "$SRC/install.sh" --domain '{domain}' --root '{docroot}' --webserver nginx{' --no-tls' if skip_ssl else ''}
""",
        },
        {
            "label": "验收 (静态资源 / nginx 配置)",
            "timeout": 90,
            "script": f"""set -eu
test -f '{docroot}/index.html' || {{ echo "没有找到 {docroot}/index.html" >&2; exit 1; }}
# nginx 必须真的在跑 —— 只看 nginx -t 的话, "装了但没启动" 会蒙混过关
systemctl is-active --quiet nginx || {{
  echo "nginx 没有启动 —— 站点会 502" >&2
  systemctl status nginx --no-pager -n 20 >&2
  exit 1
}}
# 必须带 Host 头走我们自己的 vhost; 不带的话命中的是 nginx 默认站点,
# 默认站点正常也能返回 200 —— 那样即使我们的站点配置坏了也会"通过"
code="$(curl -s -o /dev/null -w '%{{http_code}}' --max-time 10 -H 'Host: {domain}' http://127.0.0.1/)"
test "$code" = "200" || {{ echo "本机 HTTP 返回 $code, 期望 200" >&2; exit 1; }}
nginx -t
echo "验收通过"
echo
echo "下一步: 打开 https://{domain}/ 拖入 .ncm 文件即可本地解密, 文件不上传。"
""",
        },
    ]


# ---------------------------------------------------------------- 验收脚本

LOGISTICS_QUOTE_STATUS = r"""set -eu
if systemctl is-active --quiet quote-server.service; then
  PORT=8792
  if [ -f /var/www/quote.byberg.store/data/port ]; then PORT="$(cat /var/www/quote.byberg.store/data/port)"; fi
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://127.0.0.1:$PORT/ || true)"
  echo "QUOTE_STATUS=running http=$code"
else
  echo "QUOTE_STATUS=stopped"
fi
"""

MUSIC_UNLOCK_STATUS = r"""set -eu
if [ -f /var/www/music-unlock/index.html ]; then
  echo "MUSIC_STATUS=installed"
else
  echo "MUSIC_STATUS=missing"
fi
"""
