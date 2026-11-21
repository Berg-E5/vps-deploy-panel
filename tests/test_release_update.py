"""Updater selects the exact versioned asset and verifies its digest."""
from __future__ import annotations

import hashlib
import io
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main


HEAD = {"X-Admin-Token": "test-only-" + "a" * 32}
PAYLOAD = b"MZ" + b"x" * (1024 * 1024 + 16)
DIGEST = "sha256:" + hashlib.sha256(PAYLOAD).hexdigest()


def release(version="1.2.3", digest=DIGEST):
    tag = "v" + version
    base = f"https://github.com/Berg-E5/vps-deploy-panel/releases/download/{tag}"
    return {
        "tag_name": tag,
        "body": "notes",
        "assets": [
            {
                "name": "VPSDeployPanel-1.0.0-Setup.exe",
                "state": "uploaded",
                "browser_download_url": f"{base}/VPSDeployPanel-1.0.0-Setup.exe",
                "digest": "sha256:" + "1" * 64,
            },
            {
                "name": f"VPSDeployPanel-{version}-Desktop-Setup.exe",
                "state": "uploaded",
                "browser_download_url": f"{base}/VPSDeployPanel-{version}-Desktop-Setup.exe",
                "digest": "sha256:" + "2" * 64,
            },
            {
                "name": f"VPSDeployPanel-{version}-Setup.exe",
                "state": "uploaded",
                "browser_download_url": f"{base}/VPSDeployPanel-{version}-Setup.exe",
                "digest": digest,
            },
        ],
    }


def test_exact_release_asset_is_selected_instead_of_first_setup():
    payload = main._release_update_payload(release())
    assert payload["version"] == "1.2.3"
    assert payload["url"].endswith("/VPSDeployPanel-1.2.3-Setup.exe")
    assert payload["digest"] == DIGEST


def test_desktop_client_selects_the_desktop_installer():
    payload = main._release_update_payload(release(), desktop=True)
    assert payload["url"].endswith("/VPSDeployPanel-1.2.3-Desktop-Setup.exe")
    assert payload["digest"] == "sha256:" + "2" * 64


def test_release_asset_requires_digest_and_exact_url():
    data = release()
    data["assets"][-1]["digest"] = ""
    with pytest.raises(ValueError):
        main._select_release_asset(data, "1.2.3", "v1.2.3")
    data = release()
    data["assets"][-1]["browser_download_url"] = "https://evil.example/x-Setup.exe"
    with pytest.raises(ValueError):
        main._select_release_asset(data, "1.2.3", "v1.2.3")


def test_update_routes_require_admin_and_install_exact_version(monkeypatch):
    client = TestClient(main.app)
    assert client.get("/api/update/check").status_code == 401
    assert client.post("/api/update/install", json={"version": "1.2.3"}).status_code == 401

    monkeypatch.setattr(main, "_fetch_latest_release", lambda: release())
    monkeypatch.setattr(main, "WINDOWS_UPDATER", True)
    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(PAYLOAD))
    calls = []

    def schedule(installer):
        calls.append(installer)
        installer.unlink(missing_ok=True)
        return {"ok": True, "scheduled": True, "mode": "browser"}

    monkeypatch.setattr(main, "_schedule_update", schedule)

    check = client.get("/api/update/check", headers=HEAD)
    assert check.status_code == 200
    assert check.json()["url"].endswith("/VPSDeployPanel-1.2.3-Setup.exe")

    installed = client.post("/api/update/install", headers=HEAD, json={"version": "1.2.3"})
    assert installed.status_code == 200, installed.text
    assert installed.json() == {"ok": True, "scheduled": True, "mode": "browser"}
    assert len(calls) == 1


def test_update_is_blocked_while_a_deployment_is_active(monkeypatch):
    monkeypatch.setattr(main, "WINDOWS_UPDATER", True)
    monkeypatch.setattr(main.store, "has_active_jobs", lambda: True)
    called = []
    monkeypatch.setattr(main, "_fetch_latest_release", lambda: called.append(True))
    response = TestClient(main.app).post(
        "/api/update/install", headers=HEAD, json={"version": "1.2.3"}
    )
    assert response.status_code == 409
    assert "部署任务" in response.text
    assert called == []


def test_update_helper_stops_old_client_installs_and_restarts():
    root = Path(__file__).resolve().parents[1]
    helper = (root / "app" / "update_helper.ps1").read_text(encoding="utf-8")
    assert "Stop-Process" in helper
    assert "'/VERYSILENT'" in helper
    assert "VPSDeployPanel.exe" in helper
    assert "launcher.pyw" in helper
    assert "Start-Process" in helper


def test_scheduler_launches_helper_outside_current_process(monkeypatch, tmp_path):
    installer = tmp_path / "update.exe"
    installer.write_bytes(PAYLOAD)
    monkeypatch.setattr(main, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main, "IS_DESKTOP_CLIENT", False)
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        Path(args[args.index("-File") + 1]).unlink(missing_ok=True)
        installer.unlink(missing_ok=True)
        return SimpleNamespace(pid=123)

    monkeypatch.setattr(main.subprocess, "Popen", fake_popen)
    result = main._schedule_update(installer)
    assert result == {"ok": True, "scheduled": True, "mode": "browser"}
    assert "-InstallerPath" in captured["args"]
    assert str(installer) in captured["args"]
    assert captured["kwargs"]["close_fds"] is True


def test_frontend_waits_for_scheduled_helper_instead_of_reloading_immediately():
    root = Path(__file__).resolve().parents[1]
    script = (root / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert "install.ok&&install.scheduled" in script
    assert "更新已开始。面板会短暂停止，安装完成后自动重新打开" in script
    assert "if(!updateScheduled)" in script


@pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows PowerShell")
def test_update_helper_stops_old_process_and_runs_installer(tmp_path):
    helper = Path(__file__).resolve().parents[1] / "app" / "update_helper.ps1"
    install = tmp_path / "install"
    install.mkdir()
    dummy = install / "dummy.py"
    dummy.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    installer = tmp_path / "fake-installer.cmd"
    marker = tmp_path / "installed.txt"
    installer.write_text(
        f"@echo off\r\necho installed>\"{marker}\"\r\nexit /b 0\r\n",
        encoding="ascii",
    )
    log = tmp_path / "update.log"
    old_process = subprocess.Popen([sys.executable, str(dummy)])
    try:
        result = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(helper),
                "-InstallerPath", str(installer),
                "-InstallDir", str(install),
                "-LogPath", str(log),
                "-DelaySeconds", "0",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        old_process.wait(timeout=5)
        assert result.returncode == 0, result.stderr
        assert marker.is_file()
        assert "Installer exit code: 0" in log.read_text(encoding="utf-8-sig")
    finally:
        if old_process.poll() is None:
            old_process.kill()


def test_windows_launcher_uses_the_same_exact_asset_rule():
    root = Path(__file__).resolve().parents[1]
    launcher = runpy.run_path(str(root / "windows" / "launcher.pyw"))
    asset = launcher["_select_release_asset"](release(), "1.2.3", "v1.2.3")
    assert asset["url"].endswith("/VPSDeployPanel-1.2.3-Setup.exe")
    assert asset["digest"] == DIGEST


def test_bad_digest_never_executes_installer(monkeypatch):
    broken = release(digest="sha256:" + "0" * 64)
    monkeypatch.setattr(main, "_fetch_latest_release", lambda: broken)
    monkeypatch.setattr(main, "WINDOWS_UPDATER", True)
    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(PAYLOAD))
    called = []
    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: called.append(True))
    response = TestClient(main.app).post(
        "/api/update/install", headers=HEAD, json={"version": "1.2.3"}
    )
    assert response.status_code == 409
    assert called == []
