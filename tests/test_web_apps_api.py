"""Production API contract for the two featured self-hosted web apps."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main


HEAD = {"X-Admin-Token": "test-only-" + "a" * 32}
FACTS = {
    "OS_ID": "debian", "OS_VERSION": "12", "ARCH": "x86_64", "UID": "0",
    "FREE_KB": "3000000", "SYSTEMD": "yes", "SS_AVAILABLE": "yes",
    "DOCKER": "no", "COMPOSE": "no", "GIT_AVAILABLE": "yes",
    "TCP_80": "free", "TCP_443": "free",
    "QUOTE_PRESENT": "no", "MUSIC_PRESENT": "no",
}


class FakeSSH:
    def credential_ready(self, host): return True
    def preflight(self, host, include_hiddify=False): return dict(FACTS)
    def password_remembered(self, host_id): return False


@pytest.fixture()
def web_api(tmp_path, monkeypatch):
    store = main.Store(str(tmp_path / "web.db"))
    ssh = FakeSSH()
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "executor", ssh)
    monkeypatch.setattr(main.runner, "executor", ssh)
    client = TestClient(main.app)
    host = client.post("/api/hosts", headers=HEAD, json={
        "name": "web", "hostname": "45.32.35.195", "port": 22, "username": "root",
    })
    assert host.status_code == 200, host.text
    return client, store, host.json()


@pytest.mark.parametrize(("project", "domain"), [
    ("logistics-quote", "quote.example.com"),
    ("music-unlock", "music.example.com"),
])
def test_featured_web_apps_accept_the_ui_https_payload(web_api, project, domain):
    client, _, host = web_api
    response = client.post("/api/jobs", headers=HEAD, json={
        "host_id": host["id"], "project": project, "domain": domain,
        "access_mode": "https",
    })
    assert response.status_code == 200, response.text
    plan = response.json()["plan"]
    assert plan["executable"] is True
    assert plan["options"]["domain"] == domain
    assert plan["options"]["access_mode"] == "https"
    assert plan["options"]["tls_identity"] == domain
    assert plan["options"]["certificate_type"] == "domain"
    assert plan["options"]["ssh_ipv4"] == "45.32.35.195"
    dependency_index = next(
        index for index, step in enumerate(plan["steps"])
        if step["label"].startswith("安装缺失的系统依赖")
    )
    tls_index = next(
        index for index, step in enumerate(plan["steps"])
        if step["label"].startswith("核对域名解析")
    )
    assert dependency_index < tls_index
    dependency_script = plan["steps"][dependency_index]["script"]
    tls_script = plan["steps"][tls_index]["script"]
    assert "systemctl restart nginx" in dependency_script
    assert "systemctl is-active --quiet nginx" in dependency_script
    assert "sport = :80" not in tls_script
    assert "systemctl is-active --quiet nginx" in tls_script
    assert "certbot plugins --authenticators" in tls_script
    assert "nginx ACME" in tls_script


@pytest.mark.parametrize(("project", "domain", "marker"), [
    ("logistics-quote", "quote.example.com", "skip-ssl"),
    ("music-unlock", "music.example.com", "--no-tls"),
])
def test_featured_web_apps_local_mode_really_skips_tls(web_api, project, domain, marker):
    client, _, host = web_api
    response = client.post("/api/jobs", headers=HEAD, json={
        "host_id": host["id"], "project": project, "domain": domain,
        "access_mode": "local",
    })
    assert response.status_code == 200, response.text
    plan = response.json()["plan"]
    assert plan["options"]["access_mode"] == "local"
    assert plan["options"]["skip_ssl"] is True
    scripts = "\n".join(step["script"] for step in plan["steps"])
    assert marker in scripts
    assert "openssl x509" not in scripts


def test_web_app_api_requires_admin_token(web_api):
    client, _, host = web_api
    response = client.post("/api/jobs", json={
        "host_id": host["id"], "project": "music-unlock",
        "domain": "music.example.com", "access_mode": "https",
    })
    assert response.status_code == 401
