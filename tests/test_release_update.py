"""Updater selects the exact versioned asset and verifies its digest."""
from __future__ import annotations

import hashlib
import io
import runpy
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
    monkeypatch.setattr(main.subprocess, "run", lambda argv, **kwargs: (
        calls.append(argv) or SimpleNamespace(returncode=0)
    ))

    check = client.get("/api/update/check", headers=HEAD)
    assert check.status_code == 200
    assert check.json()["url"].endswith("/VPSDeployPanel-1.2.3-Setup.exe")

    installed = client.post("/api/update/install", headers=HEAD, json={"version": "1.2.3"})
    assert installed.status_code == 200, installed.text
    assert installed.json() == {"ok": True, "exit_code": 0}
    assert len(calls) == 1
    assert calls[0][-1] == "/CLOSEAPPLICATIONS"


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
