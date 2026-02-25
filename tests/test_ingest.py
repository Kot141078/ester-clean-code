# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import io
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# Generation of SSRF token in accordance with security/outn_rach.issue_SSRF_token():
def _csrf_for(ua: str, ip: str) -> str:
    secret = (os.getenv("CSRF_SECRET", "ester-dev-csrf-secret")).encode("utf-8")
    msg = f"{ua}|{ip}".encode("utf-8")
    sig = hmac.new(secret, msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii")


def test_ingest_upload_and_status(client, auth_hdr_operator, monkeypatch):
    ua = "pytest-agent"
    ip = "127.0.0.1"
    csrf = _csrf_for(ua, ip)

    # korrektnyy tekstovyy fayl
    data = {"file": (io.BytesIO(b"hello ester"), "note.txt")}
    headers = {
        **auth_hdr_operator,
        "User-Agent": ua,
        "X-Forwarded-For": ip,
        "X-CSRF-Token": csrf,
    }
    r = client.post("/ingest/file", data=data, headers=headers, content_type="multipart/form-data")
    assert r.status_code == 200, r.data
    job = r.get_json()
    job_id = job.get("id") or ""
    assert job_id

    # status
    r2 = client.get("/ingest/status", query_string={"id": job_id}, headers=auth_hdr_operator)
    assert r2.status_code in (
        200,
        404,
    ), r2.data  # may not yet be found instantly


def test_ingest_unsupported_type(client, auth_hdr_operator):
    ua = "pytest-agent"
    ip = "127.0.0.1"
    csrf = _csrf_for(ua, ip)

    data = {"file": (io.BytesIO(b"bin"), "data.bin")}
    headers = {
        **auth_hdr_operator,
        "User-Agent": ua,
        "X-Forwarded-For": ip,
        "X-CSRF-Token": csrf,
    }
    r = client.post("/ingest/file", data=data, headers=headers, content_type="multipart/form-data")
# assert r.status_code == 415