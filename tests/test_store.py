from app.store import Store
from app.catalog import build_plan
from tempfile import TemporaryDirectory
from pathlib import Path

import pytest

GOOD = {'OS_ID':'ubuntu','ARCH':'x86_64','UID':'0','DOCKER':'yes','COMPOSE':'yes','SYSTEMD':'yes','UDP_51820':'free'}


def test_store_creates_hosts_and_single_approval():
    with TemporaryDirectory() as td:
        s=Store(str(Path(td)/'data.db'))
        host=s.add_host({'name':'vps','hostname':'example.com','port':22,'username':'root'})
        s.save_facts(host['id'],GOOD)
        job=s.new_job(host['id'],'sing-box',build_plan('sing-box',GOOD))
        assert s.job(job['id'])['status']=='planned'
        assert s.approve(job['id']) is True
        assert s.approve(job['id']) is False
        s.log(job['id'],'checking')
        assert 'checking' in s.job(job['id'])['logs']


def test_interrupted_jobs_never_auto_resume():
    with TemporaryDirectory() as td:
        path=str(Path(td)/'state.db')
        s=Store(path)
        host=s.add_host({'name':'vps','hostname':'example.com','port':22,'username':'root'})
        job=s.new_job(host['id'],'sing-box',build_plan('sing-box',GOOD))
        s.approve(job['id'])
        recovered=Store(path)
        assert recovered.job(job['id'])['status']=='interrupted'


def test_endpoint_approval_is_atomic_across_duplicate_host_records():
    with TemporaryDirectory() as td:
        store = Store(str(Path(td) / "data.db"))
        first = store.add_host({"name": "one", "hostname": "example.com",
                                "username": "root", "port": 22})
        second = store.add_host({"name": "two", "hostname": "EXAMPLE.com",
                                 "username": "root", "port": 22})
        first_job = store.new_job(first["id"], "sing-box", {"steps": []})
        second_job = store.new_job(second["id"], "sing-box", {"steps": []})
        assert store.approve(
            first_job["id"], hostname=first["hostname"], port=first["port"]
        ) is True
        with pytest.raises(ValueError, match="SSH 地址和端口"):
            store.approve(
                second_job["id"], hostname=second["hostname"], port=second["port"]
            )
        assert store.job(second_job["id"])["status"] == "planned"


@pytest.mark.parametrize(("source_project", "upgrade_project"), [
    ("3x-ui", "3x-ui-https"),
    ("s-ui", "s-ui-https"),
])
def test_source_job_cannot_be_deleted_while_https_upgrade_depends_on_it(
    source_project, upgrade_project,
):
    with TemporaryDirectory() as td:
        store = Store(str(Path(td) / "data.db"))
        host = store.add_host({"name": "vps", "hostname": "example.com",
                               "username": "root", "port": 22})
        source = store.new_job(host["id"], source_project, {"options": {}})
        store.set_status(source["id"], "completed")
        upgrade = store.new_job(host["id"], upgrade_project, {
            "options": {"source_job_id": source["id"]},
        })

        with pytest.raises(ValueError, match="依赖"):
            store.delete_job(source["id"])
        assert store.job(source["id"]) is not None
        assert store.job(upgrade["id"]) is not None

        assert store.delete_job(upgrade["id"]) is True
        assert store.delete_job(source["id"]) is True
