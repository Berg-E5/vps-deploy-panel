r"""安装包启动器 —— 无控制台窗口运行面板并打开浏览器。

由快捷方式调用: pythonw.exe launcher.pyw
数据、日志、.env 都放在 %LOCALAPPDATA%\VPSDeployPanel, 升级覆盖安装不会丢。
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(APP_DIR))) / "VPSDeployPanel"
LOG_DIR = DATA_DIR / "logs"
PANEL_URL = "http://127.0.0.1:8787"
GITHUB_REPO = "Berg-E5/vps-deploy-panel"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _log(message: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with (LOG_DIR / "panel.log").open("a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def _env_lines(env_file: Path) -> list[str]:
    if not env_file.exists():
        return ["# VPS Deploy Panel 本机配置 (安装包生成)"]
    return env_file.read_text(encoding="utf-8-sig").splitlines()


def _env_value(lines: list[str], name: str) -> str:
    for prefix in ("VPSDEPLOY_" + name, "NETDEPLOY_" + name, name):
        for line in lines:
            if line.startswith(prefix + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _set_env_line(lines: list[str], name: str, value: str) -> list[str]:
    names = ("VPSDEPLOY_" + name, "NETDEPLOY_" + name, name)
    kept = [line for line in lines if not any(line.startswith(x + "=") for x in names)]
    kept.append(f"{name}={value}")
    return kept


def _ensure_env() -> None:
    """Persist local tokens and enable the native Codex worker by default."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env_file = DATA_DIR / ".env"
    lines = _env_lines(env_file)
    token = _env_value(lines, "ADMIN_TOKEN")
    if len(token) < 24 or token.startswith("REPLACE_"):
        token = secrets.token_urlsafe(40)
        lines = _set_env_line(lines, "VPSDEPLOY_ADMIN_TOKEN", token)
        _log("已生成新的管理员令牌")

    auto_value = _env_value(lines, "CODEX_AUTO_START") or os.environ.get(
        "VPSDEPLOY_CODEX_AUTO_START", "1"
    )
    auto_codex = auto_value.strip() != "0"
    worker_token = _env_value(lines, "WORKER_TOKEN")
    if auto_codex and (len(worker_token) < 24 or worker_token.startswith("REPLACE_")):
        worker_token = secrets.token_urlsafe(40)
        lines = _set_env_line(lines, "VPSDEPLOY_WORKER_TOKEN", worker_token)
        _log("已生成本机 Codex Worker 连接令牌")

    env_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.environ["VPSDEPLOY_ADMIN_TOKEN"] = token
    os.environ["VPSDEPLOY_DATA"] = str(DATA_DIR)
    os.environ["VPSDEPLOY_LOCAL_AUTO_LOGIN"] = "1"
    if auto_codex:
        os.environ["VPSDEPLOY_CODEX_AUTO_START"] = "1"
        os.environ["VPSDEPLOY_CODEX_NATIVE_AUTO_START"] = "1"
        os.environ["VPSDEPLOY_CODEX_WORKER_URL"] = "http://127.0.0.1:8789"
        os.environ["VPSDEPLOY_WORKER_TOKEN"] = worker_token
    else:
        os.environ["VPSDEPLOY_CODEX_AUTO_START"] = "0"
        os.environ["VPSDEPLOY_CODEX_NATIVE_AUTO_START"] = "0"
        os.environ["VPSDEPLOY_CODEX_WORKER_URL"] = ""
        os.environ["VPSDEPLOY_WORKER_TOKEN"] = ""


def _port_is_free(port: int) -> bool:
    """端口是否可用。绑一下再松开, 比查进程表可靠。

    注意: 绝对不要设 SO_REUSEADDR。Windows 上它允许另一个进程强行
    绑定同一个端口, 于是探测会"成功", 但真正 listen 时端口被别人占着,
    面板起来却不服务任何请求 —— 而 pythonw 没有控制台, 用户只看到
    "双击了没反应"。宁可多试一个端口。
    """
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            # 独占绑定: 别人在用就一定失败
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except OSError:
                pass
        try:
            sock.bind(("127.0.0.1", port))
            sock.listen(1)
        except OSError:
            return False
    return True


def _pick_port(preferred: int) -> int:
    """优先用 8787; 被占用就往后找一个空闲端口。

    端口冲突时必须换端口, 不能直接失败 —— pythonw 没有控制台,
    启动失败在用户那里就是"双击了没反应", 完全看不出原因。
    """
    if _port_is_free(preferred):
        return preferred
    for candidate in range(preferred + 1, preferred + 20):
        if _port_is_free(candidate):
            _log(f"端口 {preferred} 被占用, 改用 {candidate}")
            return candidate
    raise RuntimeError(f"{preferred}-{preferred + 19} 都被占用")


def _open_browser(base_url: str) -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(f"{base_url}/api/health", timeout=2) as resp:
                if resp.status == 200:
                    import webbrowser
                    webbrowser.open(base_url)
                    return
        except Exception:
            pass
        time.sleep(0.5)


def _select_release_asset(data: dict, version: str, tag: str | None = None) -> dict:
    expected = f"VPSDeployPanel-{version}-Setup.exe"
    matches = [
        asset for asset in data.get("assets", [])
        if isinstance(asset, dict) and asset.get("name") == expected
        and asset.get("state", "uploaded") == "uploaded"
    ]
    if len(matches) != 1:
        raise ValueError(f"Release 中必须存在且仅存在一个 {expected}")
    asset = matches[0]
    url = str(asset.get("browser_download_url", ""))
    parsed = urlparse(url)
    tag = tag or f"v{version}"
    prefix = f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/{expected}"
    if (parsed.scheme != "https" or parsed.hostname != "github.com"
            or parsed.username or parsed.password or not url.startswith(prefix)):
        raise ValueError("更新包地址不是预期的 GitHub Release")
    digest = str(asset.get("digest", "")).lower()
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise ValueError("更新包缺少 SHA-256 摘要")
    return {"url": url, "digest": digest}


def check_for_updates() -> dict:
    """Only accept the exact versioned main installer and its SHA-256 digest."""
    try:
        req = urllib.request.Request(GITHUB_API, headers={"User-Agent": "VPSDeployPanel-Updater"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        latest_version = str(data.get("tag_name", "")).strip().lstrip("v")
        if not re.fullmatch(r"\d+\.\d+\.\d+", latest_version):
            raise ValueError("Release 版本号格式不正确")
        current_version = "1.0.1"
        asset = _select_release_asset(data, latest_version, str(data.get("tag_name", "")))
        return {
            "has_update": _version_greater(latest_version, current_version),
            "version": latest_version,
            "current": current_version,
            "url": asset["url"],
            "digest": asset["digest"],
            "notes": data.get("body", "")[:2000],
        }
    except Exception as exc:
        return {"has_update": False, "error": str(exc)}


def _version_greater(a: str, b: str) -> bool:
    """简单语义化版本比较：1.0.1 > 1.0.0"""
    try:
        a_parts = [int(x) for x in a.split(".")]
        b_parts = [int(x) for x in b.split(".")]
        # Pad to same length
        max_len = max(len(a_parts), len(b_parts))
        a_parts += [0] * (max_len - len(a_parts))
        b_parts += [0] * (max_len - len(b_parts))
        return a_parts > b_parts
    except Exception:
        return False


def download_and_install_update(url: str, digest: str) -> bool:
    """Download the exact GitHub asset, verify SHA-256, then install it."""
    installer_path = None
    try:
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.hostname != "github.com"
                or parsed.username or parsed.password
                or not url.startswith(f"https://github.com/{GITHUB_REPO}/releases/download/")):
            raise ValueError("更新包地址不受信任")
        expected = digest.lower()
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", expected):
            raise ValueError("更新包摘要格式不正确")
        fd, raw_path = tempfile.mkstemp(prefix="vpsdeploy-update-", suffix=".exe")
        os.close(fd)
        installer_path = Path(raw_path)
        _log(f"下载更新包: {url}")
        digest_hash = hashlib.sha256()
        total = 0
        with urllib.request.urlopen(url, timeout=60) as response, installer_path.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 250 * 1024 * 1024:
                    raise ValueError("更新包超过 250 MB 安全上限")
                digest_hash.update(chunk)
                output.write(chunk)
        if total < 1024 * 1024:
            raise ValueError("更新包大小异常")
        if not secrets.compare_digest(digest_hash.hexdigest(), expected.split(":", 1)[1]):
            raise ValueError("更新包 SHA-256 校验失败")
        _log(f"下载完成，静默安装: {installer_path}")
        result = subprocess.run(
            [str(installer_path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
            timeout=300,
            capture_output=True,
        )
        return result.returncode == 0
    except Exception as exc:
        _log(f"更新失败: {exc}")
        return False
    finally:
        if installer_path is not None:
            installer_path.unlink(missing_ok=True)


def main() -> int:
    _ensure_env()
    sys.path.insert(0, str(APP_DIR))
    try:
        port = _pick_port(8787)
    except RuntimeError as exc:
        _log(f"找不到可用端口: {exc}")
        return 1
    base_url = f"http://127.0.0.1:{port}"
    # The API uses the actual loopback port when granting the opt-in local
    # session; a hard-coded 8787 would break whenever it falls back.
    os.environ["VPSDEPLOY_LOCAL_PORT"] = str(port)
    # 把端口写下来, 用户能找到面板实际在哪
    try:
        (DATA_DIR / "port").write_text(str(port), encoding="utf-8")
    except OSError:
        pass
    _log(f"面板启动于 {base_url}")
    threading.Thread(target=_open_browser, args=(base_url,), daemon=True).start()
    try:
        import uvicorn
    except Exception as exc:
        _log(f"无法加载运行库: {exc}")
        return 1
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_config=None,
                    access_log=False)
    except Exception as exc:
        _log(f"面板启动失败: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
