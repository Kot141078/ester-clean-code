# -*- coding: utf-8 -*-
import time
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_ingest_submit_path_and_poll(client, auth_header, app, tmp_path):
    # Podgotovim fayl
    src = tmp_path / "doc.txt"
    src.write_text("Zagolovok\n\nEto testovoe soderzhimoe.\n" * 10, encoding="utf-8")

    # Otpravim po puti
    r = client.post("/ingest/submit", json={"path": str(src), "user": "Tester"}, headers=auth_header)
    assert r.status_code == 200
    job_id = r.get_json()["job_id"]

    # Opros statusa, zhdem zaversheniya
    done = None
    t0 = time.time()
    while time.time() - t0 < 6.0:
        s = client.get(f"/ingest/job/{job_id}", headers=auth_header)
        assert s.status_code == 200
        job = s.get_json()["job"]
        if job["status"] in ("done", "error"):
            done = job
            break
        time.sleep(0.1)
    assert done, "Zadacha inzhesta ne zavershilas vovremya"
    assert done["status"] == "done", f"ingest error: {done.get('error')}"
    assert done["stats"]["vstore_added"] >= 1

def test_ingest_submit_upload(client, auth_header):
    # multipart upload
    data = {
        "user": (None, "Owner"),
        "collection": (None, "tests"),
        "file": ("note.txt", "Tekstovyy fayl dlya zagruzki.\nStroka 2.".encode("utf-8"), "text/plain"),
    }
    r = client.post("/ingest/submit", data=data, headers=auth_header, content_type="multipart/form-data")
    assert r.status_code == 200
    job_id = r.get_json()["job_id"]
    assert isinstance(job_id, str) and len(job_id) > 0
