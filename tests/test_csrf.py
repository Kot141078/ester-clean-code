# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import io
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _csrf_for(ua: str, ip: str) -> str:
    secret = (os.getenv("CSRF_SECRET", "ester-dev-csrf-secret")).encode("utf-8")
    msg = f"{ua}|{ip}".encode("utf-8")
    sig = hmac.new(secret, msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii")


def test_form_post_without_csrf_is_denied(client, auth_hdr_operator):
    # multipart/form-data bez X-CSRF-Token -> 403
    data = {"file": (io.BytesIO(b"hello"), "a.txt")}
    headers = {
        **auth_hdr_operator,
        "User-Agent": "pytest-agent",
        "X-Forwarded-For": "127.0.0.1",
    }
    r = client.post("/ingest/file", data=data, headers=headers, content_type="multipart/form-data")
    # Esli CSRF vyklyuchen/ne trebuetsya po politike — mozhet byt 200/415; po nashey realizatsii dolzhen byt 403
    assert r.status_code == 403


def test_form_post_with_csrf_ok(client, auth_hdr_operator):
    ua = "pytest-agent"
    ip = "127.0.0.1"
    csrf = _csrf_for(ua, ip)
    data = {"file": (io.BytesIO(b"hello"), "a.txt")}
    headers = {
        **auth_hdr_operator,
        "User-Agent": ua,
        "X-Forwarded-For": ip,
        "X-CSRF-Token": csrf,
    }
    r = client.post("/ingest/file", data=data, headers=headers, content_type="multipart/form-data")
    assert r.status_code in (
        200,
        415,
)  # tip dopustim/nedopustim — glavnoe, chto ne 403