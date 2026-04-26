from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit, urlunsplit


OLLAMA_BASE = (os.getenv("OLLAMA_BASE") or "http://127.0.0.1:11434").rstrip("/")
PROXY_HOST = os.getenv("OLLAMA_PROXY_HOST") or "127.0.0.1"
PROXY_PORT = int(os.getenv("OLLAMA_PROXY_PORT") or "1234")
DEFAULT_MODEL = (os.getenv("OLLAMA_PROXY_DEFAULT_MODEL") or "").strip()
DEFAULT_REASONING_EFFORT = (os.getenv("OLLAMA_PROXY_REASONING_EFFORT") or "none").strip()
REQUEST_TIMEOUT_SEC = float(os.getenv("OLLAMA_PROXY_TIMEOUT_SEC") or "1800")


def _target_url(path: str) -> str:
    parts = urlsplit(path)
    return urlunsplit((urlsplit(OLLAMA_BASE).scheme, urlsplit(OLLAMA_BASE).netloc, parts.path, parts.query, ""))


def _should_inject_reasoning(path: str) -> bool:
    clean = path.split("?", 1)[0].rstrip("/")
    return clean.endswith("/v1/chat/completions") or clean.endswith("/chat/completions")


def _maybe_rewrite_payload(path: str, body: bytes) -> bytes:
    if not body:
        return body
    if not _should_inject_reasoning(path):
        return body

    try:
        payload: dict[str, Any] = json.loads(body.decode("utf-8"))
    except Exception:
        return body

    if DEFAULT_MODEL and not payload.get("model"):
        payload["model"] = DEFAULT_MODEL
    if DEFAULT_REASONING_EFFORT and "reasoning_effort" not in payload and "reasoning" not in payload:
        payload["reasoning_effort"] = DEFAULT_REASONING_EFFORT

    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _forward(self) -> None:
        if self.path == "/__proxy/health":
            self._write_json(
                200,
                {
                    "ok": True,
                    "ollama_base": OLLAMA_BASE,
                    "default_model": DEFAULT_MODEL,
                    "reasoning_effort": DEFAULT_REASONING_EFFORT,
                },
            )
            return

        content_length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(content_length) if content_length > 0 else b""
        body = _maybe_rewrite_payload(self.path, body)

        headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
        auth = self.headers.get("Authorization")
        if auth:
            headers["Authorization"] = auth

        req = urllib.request.Request(
            _target_url(self.path),
            data=body if self.command in {"POST", "PUT", "PATCH"} else None,
            headers=headers,
            method=self.command,
        )

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
                out = resp.read()
                self.send_response(resp.status)
                content_type = resp.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
        except urllib.error.HTTPError as exc:
            out = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
        except Exception as exc:
            self._write_json(502, {"error": f"proxy_error:{type(exc).__name__}:{exc}"})

    def do_GET(self) -> None:
        self._forward()

    def do_POST(self) -> None:
        self._forward()

    def do_DELETE(self) -> None:
        self._forward()

    def do_PUT(self) -> None:
        self._forward()

    def do_PATCH(self) -> None:
        self._forward()

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write("[ollama-proxy] " + (fmt % args) + "\n")
        sys.stdout.flush()


def main() -> int:
    server = ThreadingHTTPServer((PROXY_HOST, PROXY_PORT), ProxyHandler)
    print(
        f"[ollama-proxy] listening on http://{PROXY_HOST}:{PROXY_PORT} -> {OLLAMA_BASE} "
        f"(model={DEFAULT_MODEL or '-'} reasoning_effort={DEFAULT_REASONING_EFFORT or '-'})"
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
