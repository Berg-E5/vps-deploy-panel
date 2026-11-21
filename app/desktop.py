r"""Desktop backend entry point used by packaging/windows/VPSDeployPanel.exe.

The desktop shell passes a port-file path and starts this script with pythonw.
It must remain independent from the browser launcher, but use the same FastAPI
application, local tokens and native Codex worker.
"""
from __future__ import annotations

import argparse
import os
import secrets
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(ROOT))) / "VPSDeployPanel"
PORT_FILE = DATA_DIR / "desktop.port"


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_env(path: Path, values: dict[str, str]) -> None:
    lines = ["# VPS Deploy Panel desktop configuration"]
    lines.extend(f"{key}={value}" for key, value in sorted(values.items()))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _configure(home: Path) -> None:
    global DATA_DIR, PORT_FILE
    DATA_DIR = home
    PORT_FILE = home / "desktop.port"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env_path = DATA_DIR / ".env"
    values = _read_env(env_path)
    admin = values.get("VPSDEPLOY_ADMIN_TOKEN", "")
    if len(admin) < 24 or admin.startswith("REPLACE_"):
        admin = secrets.token_urlsafe(40)
        values["VPSDEPLOY_ADMIN_TOKEN"] = admin
    worker = values.get("VPSDEPLOY_WORKER_TOKEN", "")
    if len(worker) < 24 or worker.startswith("REPLACE_"):
        worker = secrets.token_urlsafe(40)
        values["VPSDEPLOY_WORKER_TOKEN"] = worker
    _write_env(env_path, values)

    os.environ["VPSDEPLOY_ADMIN_TOKEN"] = admin
    os.environ["VPSDEPLOY_WORKER_TOKEN"] = worker
    os.environ["VPSDEPLOY_DATA"] = str(DATA_DIR)
    os.environ["VPSDEPLOY_LOCAL_AUTO_LOGIN"] = "1"
    os.environ["VPSDEPLOY_CODEX_AUTO_START"] = values.get(
        "VPSDEPLOY_CODEX_AUTO_START",
        os.environ.get("VPSDEPLOY_CODEX_AUTO_START", "1"),
    )
    if os.environ["VPSDEPLOY_CODEX_AUTO_START"] == "0":
        os.environ["VPSDEPLOY_CODEX_NATIVE_AUTO_START"] = "0"
        os.environ["VPSDEPLOY_CODEX_WORKER_URL"] = ""
    else:
        os.environ["VPSDEPLOY_CODEX_NATIVE_AUTO_START"] = "1"
        os.environ["VPSDEPLOY_CODEX_WORKER_URL"] = "http://127.0.0.1:8789"


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
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
    for port in range(preferred, preferred + 20):
        if _port_available(port):
            return port
    raise RuntimeError("no loopback port available for the desktop panel")


def _write_port_file(path: Path, port: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(str(port), encoding="ascii")
    os.replace(temporary, path)


def _stop_existing(home: Path, port_file: Path) -> int:
    values = _read_env(home / ".env")
    token = values.get("VPSDEPLOY_ADMIN_TOKEN", "")
    try:
        port = int(port_file.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return 1
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/desktop/stop",
        data=b"",
        method="POST",
        headers={"X-Admin-Token": token},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return 0 if response.status == 200 else 1
    except (OSError, urllib.error.URLError):
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--home", default=str(DATA_DIR))
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--port-file", default="")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--stop", action="store_true")
    args, _unknown = parser.parse_known_args(argv)
    home = Path(args.home).resolve()
    port_file = Path(args.port_file).resolve() if args.port_file else home / "desktop.port"
    _configure(home)
    if args.stop:
        return _stop_existing(home, port_file)

    port = _pick_port(args.port)
    os.environ["VPSDEPLOY_LOCAL_PORT"] = str(port)
    sys.path.insert(0, str(ROOT))

    import uvicorn
    from app.main import app

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        workers=1,
        access_log=False,
        log_level="warning" if args.quiet else "info",
    )
    server = uvicorn.Server(config)
    app.state.uvicorn_server = server
    _write_port_file(port_file, port)
    try:
        server.run()
    finally:
        try:
            if port_file.read_text(encoding="ascii").strip() == str(port):
                port_file.unlink(missing_ok=True)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    # Retry only the initial local bind race; uvicorn remains authoritative.
    for _ in range(2):
        try:
            raise SystemExit(main())
        except RuntimeError:
            time.sleep(0.2)
    raise SystemExit(1)
