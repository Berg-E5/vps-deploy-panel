"""Windows QuickStart distinguishes reopening from an actual update."""
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_launcher_reuses_running_panel_before_the_update():
    launcher = (ROOT / "scripts" / "QuickStart-Windows.ps1").read_text(encoding="utf-8-sig")
    existing, update = launcher.split("$update = ", 1)
    assert "Get-VPSDeployPanelVersion" in existing
    assert "$health.security -ceq 'local-only'" in existing
    assert "Start-Process $panelUrl\n        return" in existing
    assert "Update-Windows.ps1" in update


@pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows PowerShell")
def test_loopback_port_probe_releases_its_socket_and_detects_real_listeners():
    script = """
$ErrorActionPreference = 'Stop'
. ./scripts/Windows-Loopback.ps1
function Get-NetTCPConnection { throw 'CIM listener data must not be used' }
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = $listener.LocalEndpoint.Port
try {
    if (Test-VPSDeployPanelPortAvailable -Port $port) { throw 'Accepted an active listener' }
} finally {
    $listener.Stop()
}
if (-not (Test-VPSDeployPanelPortAvailable -Port $port)) { throw 'Stopped listener left port blocked' }
if (-not (Test-VPSDeployPanelPortAvailable -Port $port)) { throw 'Probe leaked its socket' }
"""
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        cwd=ROOT,
        check=True,
        timeout=15,
    )


def test_windows_installer_contains_desktop_backend_and_codex_requirements():
    desktop = ROOT / "app" / "desktop.py"
    assert desktop.is_file()
    assert "uvicorn.Server" in desktop.read_text(encoding="utf-8")
    assert "app/desktop.py" in (ROOT / "packaging" / "windows" / "Launcher.cs").read_text(encoding="utf-8")
    builder = (ROOT / "windows" / "build-installer.ps1").read_text(encoding="utf-8-sig")
    assert "requirements-codex-worker.txt" in builder
    installer = (ROOT / "windows" / "installer.iss").read_text(encoding="utf-8")
    assert 'Source: "build\\requirements-codex-worker.txt"' in installer
    assert r"{localappdata}\{#AppNameLower}" in installer
    assert r"{userappdata}\{#AppNameLower}" not in installer
    launcher = (ROOT / "windows" / "launcher.pyw").read_text(encoding="utf-8-sig")
    assert 'auto_value = _env_value(lines, "CODEX_AUTO_START")' in launcher
    assert 'os.environ["VPSDEPLOY_CODEX_NATIVE_AUTO_START"] = "1"' in launcher
    assert "VPSDEPLOY_WORKER_TOKEN" in launcher
    assert "secrets.token_urlsafe(40)" in launcher
    assert "VPSDEPLOY_LOCAL_PORT" in launcher


def test_release_workflow_builds_and_publishes_all_windows_assets():
    workflow = (ROOT / ".github" / "workflows" / "windows-installer.yml").read_text(encoding="utf-8")
    assert "packaging\\windows\\build.py" in workflow
    assert "VPSDeployPanel-$version-Desktop-Setup.exe" in workflow
    assert "VPSDeployPanel-$version-portable.zip" in workflow
    assert "SHA256SUMS.txt" in workflow
    assert "gh release create" in workflow
    assert "gh release upload" in workflow


def test_current_version_is_consistent_between_server_frontend_and_docs():
    root = Path(__file__).resolve().parents[1]
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "app" / "static" / "app.js").read_text(encoding="utf-8")
    assert 'version="1.0.2"' in main
    assert 'version="1.0.2"' in main
    assert "ALPHA v1.0.2" in html
    assert "const CLIENT_VERSION = '1.0.2'" in js
    assert "api('/health')" in js
    assert "版本不一致" in js
