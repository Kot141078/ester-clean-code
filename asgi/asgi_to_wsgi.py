# -*- coding: utf-8 -*-
"""asgi/asgi_to_wsgi.py - minimalnyy adapter ASGI -> WSGI.

Zemnoy abzats:
Pozvolyaet montirovat ASGI (FastAPI) pod WSGI (Flask) bez zavisimosti
na AsgiToWsgi iz asgiref, kotoraya mozhet otsutstvovat v novykh versiyakh."""
from __future__ import annotations

from http import HTTPStatus
from typing import Iterable, List, Tuple

from asgiref.sync import AsyncToSync
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _status_line(status_code: int) -> str:
    try:
        phrase = HTTPStatus(status_code).phrase
    except Exception:
        phrase = "OK"
    return f"{status_code} {phrase}"


def _build_headers(environ) -> List[Tuple[bytes, bytes]]:
    headers: List[Tuple[bytes, bytes]] = []

    # Standard WSGI-to-ASGI header mapping
    for key, value in environ.items():
        if not isinstance(key, str):
            continue
        if key.startswith("HTTP_"):
            name = key[5:].replace("_", "-").lower().encode("latin1")
            headers.append((name, str(value).encode("latin1")))

    # Content-Type and Content-Length are special-cased in WSGI
    if "CONTENT_TYPE" in environ:
        headers.append((b"content-type", str(environ["CONTENT_TYPE"]).encode("latin1")))
    if "CONTENT_LENGTH" in environ and str(environ["CONTENT_LENGTH"]).strip():
        headers.append((b"content-length", str(environ["CONTENT_LENGTH"]).encode("latin1")))

    return headers


class AsgiToWsgi:
    """
    Minimal ASGI->WSGI adapter (sync WSGI callable).
    Covers common HTTP request/response flow.
    """

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    def __call__(self, environ, start_response) -> Iterable[bytes]:
        content_length = environ.get("CONTENT_LENGTH")
        try:
            length = int(content_length) if content_length else 0
        except Exception:
            length = 0
        body = environ["wsgi.input"].read(length if length > 0 else -1) or b""

        path = environ.get("PATH_INFO", "") or "/"
        script_name = environ.get("SCRIPT_NAME", "") or ""
        query_string = environ.get("QUERY_STRING", "") or ""

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": (environ.get("SERVER_PROTOCOL", "HTTP/1.1").split("/", 1)[-1]),
            "method": environ.get("REQUEST_METHOD", "GET"),
            "scheme": environ.get("wsgi.url_scheme", "http"),
            "path": path,
            "raw_path": path.encode("utf-8"),
            "root_path": script_name,
            "query_string": query_string.encode("ascii", "ignore"),
            "headers": _build_headers(environ),
            "client": (
                (environ.get("REMOTE_ADDR"), int(environ.get("REMOTE_PORT", 0) or 0))
                if environ.get("REMOTE_ADDR")
                else None
            ),
            "server": (
                environ.get("SERVER_NAME"),
                int(environ.get("SERVER_PORT", 80) or 80),
            ),
        }

        response_status = {"code": 500}
        response_headers: List[Tuple[str, str]] = []
        response_body: List[bytes] = []

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                response_status["code"] = int(message.get("status", 500))
                raw_headers = message.get("headers", []) or []
                response_headers.clear()
                for k, v in raw_headers:
                    if isinstance(k, bytes):
                        k = k.decode("latin1")
                    if isinstance(v, bytes):
                        v = v.decode("latin1")
                    response_headers.append((k, v))
            elif message["type"] == "http.response.body":
                response_body.append(message.get("body", b"") or b"")

        AsyncToSync(self.asgi_app)(scope, receive, send)

        start_response(_status_line(response_status["code"]), response_headers)
        return [b"".join(response_body)]


__all__ = ["AsgiToWsgi"]