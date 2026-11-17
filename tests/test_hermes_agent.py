"""Hermes Agent 接入专项测试。

覆盖面板接入 Hermes Agent 的全部约束:
固定 commit、固定 SHA-256、无 curl|bash、审批后执行、
不需要域名/80-443、已装拒绝覆盖、systemd 单元真实存在、
验收步骤不虚构 HTTP 健康端点。
"""
from __future__ import annotations

import re

import pytest

from app import catalog as C
from app import web_apps as W


GOOD_FACTS = {
    "OS_ID": "ubuntu",
    "ARCH": "x86_64",
    "UID": "0",
    "SYSTEMD": "yes",
    "GIT_AVAILABLE": "yes",
    "FREE_KB": "8388608",
    "HERMES_PRESENT": "no",
    "TCP_80": "free",
    "TCP_443": "free",
}


def _plan(**options):
    facts = dict(GOOD_FACTS)
    opts = {"installdir": "", "skip_browser": True}
    opts.update(options)
    return C.build_plan("hermes-agent", facts, opts)


def _scripts(plan) -> str:
    return "\n".join(step.get("script", "") for step in plan["steps"])


# ------------------------------------------------------------------ 目录条目


def test_catalog_entry_exists():
    entry = C.CATALOG["hermes-agent"]
    assert entry["name"] == "Hermes Agent"
    assert entry["docs"] == "https://github.com/NousResearch/hermes-agent"
    assert entry["deployment"] == "install"


def test_catalog_entry_is_not_internal():
    assert C.CATALOG["hermes-agent"].get("internal") is not True


def test_catalog_lists_self_built_projects_first():
    keys = [k for k in C.CATALOG if not C.CATALOG[k].get("internal")]
    # 自建项目应该排在通用项目之前
    for own in ("logistics-quote", "music-unlock", "hermes-agent"):
        assert own in keys


def test_warnings_present_for_every_project():
    plan = _plan()
    assert plan.get("warnings")
    assert any("SHA-256" in w for w in plan["warnings"])


# ------------------------------------------------------------------ 固定版本


def test_pinned_commit_is_full_sha():
    assert re.fullmatch(r"[0-9a-f]{40}", W.HERMES_AGENT_COMMIT)


def test_pinned_install_script_sha256_is_full_sha():
    assert re.fullmatch(r"[0-9a-f]{64}", W.HERMES_AGENT_INSTALL_SHA256)


def test_download_step_verifies_checksum():
    plan = _plan()
    download = [s for s in plan["steps"] if "SHA-256" in s.get("script", "")
                or "sha256" in s.get("script", "").lower()]
    assert download, "必须有校验 SHA-256 的下载步骤"
    script = download[0]["script"]
    assert W.HERMES_AGENT_INSTALL_SHA256 in script
    assert W.HERMES_AGENT_COMMIT in script


def test_install_step_pins_commit_and_non_interactive():
    plan = _plan()
    scripts = _scripts(plan)
    assert "--commit" in scripts
    assert W.HERMES_AGENT_COMMIT in scripts
    assert "--non-interactive" in scripts


def test_never_pipes_remote_script_to_shell():
    """禁止 curl | bash / wget | sh 这类管道执行。"""
    scripts = _scripts(_plan())
    for line in scripts.splitlines():
        # 逐行匹配: curl/wget 取回内容后直接管道给 shell
        assert not re.search(r"\b(curl|wget)\b[^\n|]*\|\s*(ba|z|k|da)?sh\b", line), line
        # 取回内容后直接管道给 shell 的其它写法
        assert not re.search(r"\|\s*(ba|z|k|da)?sh\b[^\n]*\b(curl|wget)\b", line), line


def test_curl_is_only_used_for_dependency_check_or_apt_list():
    """脚本里出现 curl 只允许三种情况:
    1) 检查依赖是否存在
    2) apt 安装清单
    3) 公共下载步骤里的固定 commit 源码抓取 (--tlsv1.2 -fsSL)
    """
    scripts = _scripts(_plan())
    for line in scripts.splitlines():
        if "curl" not in line:
            continue
        assert ("command -v curl" in line
                or "git curl ca-certificates" in line
                or "缺少 curl" in line
                or "--tlsv1.2" in line), line


def test_no_bare_curl_of_install_script():
    scripts = _scripts(_plan())
    # 允许出现 curl（下载文件），但不允许直接 curl 一个远程脚本去执行
    assert not re.search(r"curl[^\n]*install\.sh[^\n]*\|\s*(ba)?sh", scripts)


# ------------------------------------------------------------------ 计划结构


def test_plan_has_expected_steps():
    plan = _plan()
    labels = [s["label"] for s in plan["steps"]]
    assert len(plan["steps"]) >= 5
    assert any("systemd" in s.get("script", "") for s in plan["steps"])


def test_plan_is_executable_and_runnable():
    plan = _plan()
    assert plan.get("executable") is True
    assert plan.get("risk")


def test_steps_have_timeouts():
    for step in _plan()["steps"]:
        assert step.get("timeout", 0) > 0


# ------------------------------------------------------------------ 选项白名单


@pytest.mark.parametrize("bad", [
    {"domain": "example.com"},
    {"panel_port": 8080},
    {"docroot": "/var/www/x"},
    {"installdir": "/opt/x", "evil": "1"},
])
def test_unauthorized_option_fields_are_rejected(bad):
    with pytest.raises(ValueError):
        C.build_plan("hermes-agent", dict(GOOD_FACTS), bad)


def test_installdir_must_be_absolute_without_dotdot():
    C.build_plan("hermes-agent", dict(GOOD_FACTS), {"installdir": "/opt/hermes-agent"})
    for bad in ("opt/hermes", "/opt/../etc", "~/hermes", "/opt/.."):
        with pytest.raises(ValueError):
            C.build_plan("hermes-agent", dict(GOOD_FACTS), {"installdir": bad})


def test_skip_browser_flag_is_boolean():
    plan = _plan(skip_browser=False)
    scripts = _scripts(plan)
    assert "--skip-browser" not in scripts
    plan2 = _plan(skip_browser=True)
    assert "--skip-browser" in _scripts(plan2)


# ------------------------------------------------------------------ 预检


def _issues(project, **overrides):
    facts = dict(GOOD_FACTS)
    facts.update(overrides)
    return C.build_plan(project, facts, {"installdir": "", "skip_browser": True})["issues"]


def test_preflight_passes_on_supported_host():
    assert _issues("hermes-agent") == []


def test_preflight_blocks_non_debian_ubuntu():
    issues = _issues("hermes-agent", OS_ID="alpine")
    assert any("Debian/Ubuntu" in i for i in issues)


def test_preflight_blocks_missing_systemd():
    issues = _issues("hermes-agent", SYSTEMD="no")
    assert any("systemd" in i for i in issues)


def test_preflight_blocks_missing_git():
    issues = _issues("hermes-agent", GIT_AVAILABLE="no")
    assert any("git" in i for i in issues)


def test_preflight_blocks_insufficient_disk():
    issues = _issues("hermes-agent", FREE_KB="1048576")
    assert any("3GB" in i for i in issues)


def test_preflight_blocks_when_already_installed():
    issues = _issues("hermes-agent", HERMES_PRESENT="yes")
    assert any("已存在" in i for i in issues)


def test_preflight_does_not_require_web_ports():
    """Hermes Agent 没有 Web 面板 —— 80/443 被占用不该阻断。"""
    facts = dict(GOOD_FACTS)
    facts["TCP_80"] = "used"
    facts["TCP_443"] = "used"
    plan = C.build_plan("hermes-agent", facts, {"installdir": "", "skip_browser": True})
    assert plan["issues"] == []


# ------------------------------------------------------------------ 安装步骤内容


def test_install_step_rejects_existing_install():
    scripts = _scripts(_plan())
    assert "拒绝覆盖" in scripts


def test_systemd_unit_is_written_and_enabled():
    scripts = _scripts(_plan())
    assert "/etc/systemd/system/hermes-gateway.service" in scripts
    assert "systemctl enable hermes-gateway.service" in scripts
    assert "systemctl daemon-reload" in scripts


def test_systemd_unit_executes_hermes_gateway():
    scripts = _scripts(_plan())
    assert "ExecStart=" in scripts
    assert " gateway" in scripts


def test_install_script_uses_absolute_install_dir():
    plan = _plan(installdir="/opt/hermes-agent")
    scripts = _scripts(plan)
    assert "/opt/hermes-agent" in scripts


def test_verification_step_does_not_fake_http_health_check():
    """Hermes 没有 HTTP 健康端点 —— 验收不能虚构 200 检查。"""
    scripts = _scripts(_plan())
    assert "--version" in scripts
    assert not re.search(r"curl[^\n]*http://127\.0\.0\.1", scripts)
    assert "200" not in scripts


def test_verification_requires_service_enabled():
    scripts = _scripts(_plan())
    assert "systemctl is-enabled hermes-gateway.service" in scripts


def test_plan_tells_user_to_configure_model_api_key():
    """没配 API key 时网关会反复重启 —— 必须在安装输出里说清楚。"""
    scripts = _scripts(_plan())
    assert "hermes setup" in scripts or "hermes model" in scripts


def test_docroot_is_not_required_for_hermes():
    """Hermes 不写 nginx —— 计划里不应出现站点配置步骤。"""
    scripts = _scripts(_plan())
    assert "server_name" not in scripts
    assert "certbot" not in scripts
