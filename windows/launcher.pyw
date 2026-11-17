"""安装包启动器 —— 无控制台窗口运行面板并打开浏览器。

由快捷方式调用: pythonw.exe launcher.pyw
数据、日志、.env 都放在 %LOCALAPPDATA%\VPSDeployPanel, 升级覆盖安装不会丢。
"""
from __future__ import annotations

import os
import secrets
import sys
import threading
import time
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(APP_DIR))) / "VPSDeployPanel"
LOG_DIR = DATA_DIR / "logs"
PANEL_URL = "http://127.0.0.1:8787"


def _log(message: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with (LOG_DIR / "panel.log").open("a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except OSError:
        pass


def _ensure_env() -> None:
    """首次运行时生成本机管理员令牌, 写进用户数据目录。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env_file = DATA_DIR / ".env"
    token = ""
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("VPSDEPLOY_ADMIN_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
    if len(token) < 24:
        token = secrets.token_urlsafe(40)
        env_file.write_text(
            "# VPS Deploy Panel 本机配置 (安装包生成)\n"
            f"VPSDEPLOY_ADMIN_TOKEN={token}\n",
            encoding="utf-8",
        )
        _log("已生成新的管理员令牌")
    os.environ["VPSDEPLOY_ADMIN_TOKEN"] = token
    os.environ["VPSDEPLOY_DATA"] = str(DATA_DIR)
    os.environ["VPSDEPLOY_LOCAL_AUTO_LOGIN"] = "1"
    os.environ["VPSDEPLOY_CODEX_AUTO_START"] = "0"


def _open_browser() -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(f"{PANEL_URL}/api/health", timeout=2) as resp:
                if resp.status == 200:
                    import webbrowser
                    webbrowser.open(PANEL_URL)
                    return
        except Exception:
            pass
        time.sleep(0.5)


def main() -> int:
    _ensure_env()
    sys.path.insert(0, str(APP_DIR))
    threading.Thread(target=_open_browser, daemon=True).start()
    try:
        import uvicorn
    except Exception as exc:
        _log(f"无法加载运行库: {exc}")
        return 1
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8787, log_config=None,
                    access_log=False)
    except Exception as exc:
        _log(f"面板启动失败: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
