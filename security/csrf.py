# -*- coding: utf-8 -*-
"""security/csrf.py - prostaya CSRF-zaschita dlya HTML-form (multipart/x-www-form-urlencoded).
Mekhanizm: server generate token i kladet cookie 'csrf_token'; client peredaet
zagolovok 'X-CSRF-Token' s tem zhe znacheniem. Dlya JSON-zaprosov zaschita otklyuchena.

Use:
  from security.csrf import csrf_protect, issue_csrf
  @app.get("/forms/token"): return issue_csrf()
  @app.post("/forms/echo"): @csrf_protect"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from functools import wraps
from typing import Callable

from flask import jsonify, make_response, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _secret() -> bytes:
    key = os.getenv("CSRF_SECRET", os.getenv("JWT_SECRET", "devsecret"))
    return key.encode("utf-8")


def _mk_token() -> str:
    msg = str(int(time.time())).encode("utf-8")
    mac = hmac.new(_secret(), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(msg + b"." + mac).decode("ascii")


def issue_csrf():
    token = _mk_token()
    resp = make_response(jsonify({"ok": True, "csrf_token": token}))
    resp.set_cookie("csrf_token", token, httponly=False, samesite="Lax")
    return resp


def _is_form_request() -> bool:
    ct = (request.content_type or "").lower()
    return ("application/x-www-form-urlencoded" in ct) or ("multipart/form-data" in ct)


def csrf_protect(fn: Callable):
    @wraps(fn)
    def _wrap(*args, **kwargs):
        if not _is_form_request():
            return fn(*args, **kwargs)
        cookie = request.cookies.get("csrf_token", "")
        header = request.headers.get("X-CSRF-Token", "")
        if not cookie or not header or not hmac.compare_digest(cookie, header):
            return jsonify({"ok": False, "error": "csrf required"}), 403
        return fn(*args, **kwargs)

# return _wrap