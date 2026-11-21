from app.tasks import JobRunner, sanitize, summarize_output
from app.store import Store
from app.catalog import build_plan
from tempfile import TemporaryDirectory
from contextlib import closing
from pathlib import Path
from time import sleep
import threading

import pytest

FACTS={'OS_ID':'debian','ARCH':'x86_64','UID':'0','FREE_KB':'1000000','DOCKER':'yes','COMPOSE':'yes','UDP_51820':'free','SYSTEMD':'yes','XUI_PRESENT':'no','SS_AVAILABLE':'yes'}

def wait_for_worker(runner, host):
    """Status can become terminal before background writes are fully done."""
    lock = runner._locks[runner.endpoint_key(host)]
    assert lock.acquire(timeout=10), "Background worker did not release its VPS lock"
    lock.release()


class StubExecutor:
    def __init__(self):self.scripts=[]
    def run(self,host,script,timeout=30):
        self.scripts.append(script)
        return 'done\n'


def test_job_approval_and_audited_execution():
    with TemporaryDirectory() as td:
        s=Store(str(Path(td)/'data.db'))
        h=s.add_host({'name':'vps','hostname':'example.com','username':'root','port':22})
        s.save_facts(h['id'],FACTS)
        plan=build_plan('sing-box',FACTS)
        j=s.new_job(h['id'],'sing-box',plan)
        fake=StubExecutor()
        runner=JobRunner(s,fake)
        runner.enqueue(j,h,'DEPLOY sing-box TO example.com')
        for _ in range(50):
            if s.job(j['id'])['status']=='completed':break
            sleep(.02)
        wait_for_worker(runner, h)
        assert s.job(j['id'])['status']=='completed'
        assert len(fake.scripts)==len(plan['steps'])
        assert s.job(j['id'])['logs'].count('通过：')==3


def test_endpoint_lock_blocks_parallel_alias_hosts_and_other_runner():
    class BlockingExecutor(StubExecutor):
        def __init__(self):
            super().__init__()
            self.entered = threading.Event()
            self.release = threading.Event()

        def run(self, host, script, timeout=30):
            self.scripts.append(script)
            self.entered.set()
            assert self.release.wait(5), "test executor was not released"
            return "done"

    with TemporaryDirectory() as td:
        store = Store(str(Path(td) / "data.db"))
        first = store.add_host({"name": "alias-1", "hostname": "example.com",
                                "username": "root", "port": 22})
        second = store.add_host({"name": "alias-2", "hostname": "EXAMPLE.com",
                                 "username": "root", "port": 22})
        for host in (first, second):
            store.save_facts(host["id"], FACTS)
        plan = build_plan("sing-box", FACTS)
        first_job = store.new_job(first["id"], "sing-box", plan)
        second_job = store.new_job(second["id"], "sing-box", plan)

        executor = BlockingExecutor()
        runner = JobRunner(store, executor)
        runner.enqueue(first_job, first, "DEPLOY sing-box TO example.com")
        assert executor.entered.wait(2)

        with pytest.raises(ValueError, match="服务器|SSH"):
            runner.enqueue(second_job, second, "DEPLOY sing-box TO EXAMPLE.com")
        other_runner = JobRunner(store, StubExecutor())
        with pytest.raises(ValueError, match="SSH"):
            other_runner.enqueue(
                store.job(second_job["id"]), second,
                "DEPLOY sing-box TO EXAMPLE.com",
            )

        executor.release.set()
        wait_for_worker(runner, first)
        assert store.job(first_job["id"])["status"] == "completed"
        assert store.job(second_job["id"])["status"] == "planned"


def test_xui_install_is_approved_and_runs_only_frozen_steps():
    with TemporaryDirectory() as td:
        store=Store(str(Path(td)/'data.db'))
        host=store.add_host({'name':'xui','hostname':'example.com','username':'root','port':22})
        store.save_facts(host['id'],FACTS)
        plan=build_plan('3x-ui',FACTS,{'panel_port':25443})
        job=store.new_job(host['id'],'3x-ui',plan)
        executor=StubExecutor()
        runner=JobRunner(store,executor)
        try:
            runner.enqueue(job,host,'INVALID CONFIRMATION')
        except ValueError:
            pass
        assert executor.scripts==[]
        runner.enqueue(job,host,'DEPLOY 3x-ui TO example.com')
        for _ in range(100):
            if store.job(job['id'])['status']=='completed':break
            sleep(.01)
        wait_for_worker(runner, host)
        assert store.job(job['id'])['status']=='completed'
        assert executor.scripts==[step['script'] for step in plan['steps']]
        assert len(executor.scripts)==5
        assert 'password=' not in store.job(job['id'])['logs'].lower()


def test_xui_tampered_options_cannot_change_remote_commands():
    with TemporaryDirectory() as td:
        store=Store(str(Path(td)/'data.db'))
        host=store.add_host({'name':'xui','hostname':'example.com','username':'root','port':22})
        store.save_facts(host['id'],FACTS)
        job=store.new_job(host['id'],'3x-ui',build_plan('3x-ui',FACTS,{'panel_port':25443}))
        import sqlite3,json
        with closing(sqlite3.connect(store.path)) as db,db:
            j=store.job(job['id'])
            j['plan']['options']={'panel_port':26500}
            db.execute('UPDATE jobs SET plan_json=? WHERE id=?',(json.dumps(j['plan']),j['id']))
        executor=StubExecutor()
        runner=JobRunner(store,executor)
        runner.enqueue(store.job(job['id']),host,'DEPLOY 3x-ui TO example.com')
        for _ in range(100):
            if store.job(job['id'])['status']=='failed':break
            sleep(.01)
        wait_for_worker(runner, host)
        assert store.job(job['id'])['status']=='failed'
        assert executor.scripts==[]


def test_xui_installed_but_certificate_failed_is_partial_not_reinstalled():
    """If certificate setup fails after step 5, preserve the installed panel."""
    from app.executor import SSHError

    class CertbotFailureExecutor(StubExecutor):
        def run(self, host, script, timeout=30):
            self.scripts.append(script)
            if len(self.scripts) == 7:
                raise SSHError("Certbot not available - test failure")
            return "stage passed\\n"

    with TemporaryDirectory() as td:
        store = Store(str(Path(td) / "data.db"))
        host = store.add_host({'name': 'xui', 'hostname': 'panel.example.com',
                               'username': 'root', 'port': 22})
        store.save_facts(host['id'], FACTS)
        plan = build_plan('3x-ui', FACTS, {
            'panel_port': 24443, 'access_mode': 'https',
            'tls_identity': 'panel.example.com'
        })
        job = store.new_job(host['id'], '3x-ui', plan)
        ssh = CertbotFailureExecutor()
        runner = JobRunner(store, ssh)
        runner.enqueue(job, host, 'DEPLOY 3x-ui TO panel.example.com')
        for _ in range(100):
            if store.job(job['id'])['status'] == 'partial':
                break
            sleep(.01)
        wait_for_worker(runner, host)
        state = store.job(job['id'])
        assert state['status'] == 'partial'
        assert len(ssh.scripts) == 7
        assert state['logs'].count('通过：') == 6
        assert 'HTTPS 未完成' in state['logs']
        assert 'secret' not in state['logs'].lower()


def test_existing_xui_https_upgrade_executes_only_certificate_steps():
    """Reconstructed source-controlled upgrade must not rerun 3X-UI installer."""
    with TemporaryDirectory() as td:
        store = Store(str(Path(td) / "data.db"))
        host = store.add_host({'name':'xui','hostname':'panel.example.com',
                               'username':'root','port':22})
        facts = dict(FACTS, XUI_PRESENT='yes')
        store.save_facts(host['id'], facts)
        options = {'panel_port': 24443, 'tls_identity':'panel.example.com',
                   'source_job_id':'a'*16}
        plan = build_plan('3x-ui-https', facts, options)
        assert plan['options']['certificate_type'] == 'domain'
        job = store.new_job(host['id'], '3x-ui-https', plan)
        ssh = StubExecutor()
        runner = JobRunner(store, ssh)
        runner.enqueue(job, host, 'DEPLOY 3x-ui-https TO panel.example.com')
        for _ in range(100):
            if store.job(job['id'])['status'] == 'completed':
                break
            sleep(.01)
        wait_for_worker(runner, host)
        assert store.job(job['id'])['status'] == 'completed'
        assert len(ssh.scripts) == 4
        assert all('/var/lib/vpsdeploy/3x-ui/install-' not in x for x in ssh.scripts)


def test_certificate_mode_tampering_blocks_execution():
    """A changed certificate mode must never bypass audited script checks."""
    with TemporaryDirectory() as td:
        store = Store(str(Path(td) / 'data.db'))
        host = store.add_host({'name':'xui','hostname':'panel.example.com',
                               'username':'root','port':22})
        store.save_facts(host['id'], FACTS)
        plan = build_plan('3x-ui', FACTS, {'panel_port':24443,
            'access_mode':'https','tls_identity':'panel.example.com'})
        job = store.new_job(host['id'], '3x-ui', plan)
        import json, sqlite3
        with closing(sqlite3.connect(store.path)) as db, db:
            saved = store.job(job['id'])
            saved['plan']['options']['certificate_type'] = 'ip'
            db.execute('UPDATE jobs SET plan_json=? WHERE id=?',
                       (json.dumps(saved['plan']),job['id']))
        ssh = StubExecutor()
        runner = JobRunner(store, ssh)
        runner.enqueue(store.job(job['id']), host,
                       'DEPLOY 3x-ui TO panel.example.com')
        for _ in range(100):
            if store.job(job['id'])['status'] == 'failed':
                break
            sleep(.01)
        wait_for_worker(runner, host)
        assert store.job(job['id'])['status'] == 'failed'
        assert ssh.scripts == []


def test_secret_redaction():
    assert 'my-secret' not in sanitize('password=my-secret')
    assert 'oops' not in sanitize('token: oops')


def test_log_summary_filters_progress_and_keeps_whole_tail_lines():
    output = (
        "Collecting certbot==5.8.0\r\n"
        "Downloading wheel 135 kB\r\n"
        "Installing collected packages: certbot\r\n"
        "Successfully installed certbot-5.8.0\r\n"
        "VPSDEPLOY_CERTBOT_READY: isolated Certbot is ready\r\n"
        "Trusted certificate issued and verification passed\r\n"
    )
    summary = summarize_output(output)
    assert summary == (
        "VPSDEPLOY_CERTBOT_READY: isolated Certbot is ready\n"
        "Trusted certificate issued and verification passed"
    )
    assert "certbot-5.8.0" not in summary


def test_log_summary_never_slices_a_line_at_the_start():
    summary = summarize_output(
        "old partial y3-none-any.whl\n"
        "Local web endpoint responded\n"
        "Only localhost HTTP verified",
        max_chars=64,
    )
    assert summary == "Local web endpoint responded\nOnly localhost HTTP verified"
    assert not summary.startswith("y3-none")


def test_log_summary_redacts_secrets():
    summary = summarize_output(
        "Starting step\r\npassword=very-secret\r\nVerification passed\r\n"
    )
    assert "very-secret" not in summary
    assert "password=[REDACTED]" in summary


def test_job_runner_uses_compact_summary_for_step_output():
    class NoisyExecutor(StubExecutor):
        def run(self, host, script, timeout=30):
            self.scripts.append(script)
            return (
                "Collecting example-package\r\n"
                "Downloading wheel 135 kB\r\n"
                "Successfully installed example-package\r\n"
                "VPSDEPLOY_STEP_READY: verified\r\n"
            )

    with TemporaryDirectory() as td:
        store = Store(str(Path(td) / "data.db"))
        host = store.add_host({"name": "vps", "hostname": "example.com",
                               "username": "root", "port": 22})
        store.save_facts(host["id"], FACTS)
        plan = build_plan("sing-box", FACTS)
        job = store.new_job(host["id"], "sing-box", plan)
        executor = NoisyExecutor()
        runner = JobRunner(store, executor)
        runner.enqueue(job, host, "DEPLOY sing-box TO example.com")
        for _ in range(100):
            if store.job(job["id"])["status"] == "completed":
                break
            sleep(0.01)
        wait_for_worker(runner, host)
        logs = store.job(job["id"])["logs"]
        assert "VPSDEPLOY_STEP_READY: verified" in logs
        assert "Successfully installed" not in logs
        assert "Downloading wheel" not in logs


def test_modified_database_plan_cannot_execute_commands():
    with TemporaryDirectory() as td:
        s=Store(str(Path(td)/'data.db'))
        h=s.add_host({'name':'vps','hostname':'example.com','username':'root','port':22})
        s.save_facts(h['id'], FACTS)
        plan=build_plan('sing-box', FACTS)
        j=s.new_job(h['id'],'sing-box',plan)
        # Simulate malformed/tampered stored recipe (attacker having write access to DB).
        import sqlite3,json
        with closing(sqlite3.connect(s.path)) as db, db:
            job=s.job(j['id'])
            job['plan']['steps'][0]['script']='echo MALICIOUS'
            db.execute('UPDATE jobs SET plan_json=? WHERE id=?',(json.dumps(job['plan']),j['id']))
        fake=StubExecutor()
        runner=JobRunner(s,fake)
        runner.enqueue(s.job(j['id']),h,'DEPLOY sing-box TO example.com')
        for _ in range(100):
            if s.job(j['id'])['status']=='failed':break
            sleep(.01)
        wait_for_worker(runner, h)
        assert s.job(j['id'])['status']=='failed'
        assert fake.scripts==[]
