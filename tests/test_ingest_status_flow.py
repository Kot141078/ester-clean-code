# -*- coding: utf-8 -*-
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_ingest_status_flow_txt(client, auth_hdr_user):
    # 1) upload
    data = {"file": ("flow.txt", b"hello ester", "text/plain")}
    r = client.post(
        "/ingest/file",
        headers=auth_hdr_user,
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code in (200, 202)
    j = r.get_json()
    assert isinstance(j, dict)
    _id = j.get("id")
    if not _id:
        # esli sistema otvechaet drugim klyuchom — poprobuem sovmestimye polya
        _id = j.get("upload_id") or j.get("task_id")
    assert _id, "ozhidali id zadachi ingest"

    # 2) poll status
    for _ in range(60):
        s = client.get("/ingest/status", headers=auth_hdr_user, query_string={"id": _id})
        assert s.status_code == 200
        sj = s.get_json()
        status = (sj.get("status") or sj.get("state") or "").upper()
        if status in ("DONE", "OK", "COMPLETE"):
            break
        time.sleep(0.1)
    else:
        raise AssertionError("ingest did not complete within time")
