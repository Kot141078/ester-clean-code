# -*- coding: utf-8 -*-
"""
asgi/security_headers.py — ASGI-midlvar strogikh zagolovkov.

MOSTY:
- (Yavnyy) CSP/HSTS/X-Frame-Options/Referrer-Policy/Permissions-Policy; vklyuchenie cherez ENV.
- (Skrytyy #1) CSP zadaetsya ENV CSP_POLICY, razumnyy defolt bez inline.
- (Skrytyy #2) Myagko vklyuchaetsya: esli SECURITY_HEADERS_ENABLE=0 — midlvar ne delaet nichego.

ZEMNOY ABZATs:
Vystavlyaet «boevye» zagolovki bezopasnosti poverkh lyubogo ASGI-prilozheniya bez pravok routov.

# c=a+b
"""
from __future__ import annotations

import os
from typing import Callable, Awaitable

from starlette.types import ASGIApp, Receive, Scope, Send
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_DEFAULT_CSP = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"

class SecurityHeaders:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.enabled = os.getenv("SECURITY_HEADERS_ENABLE","1") == "1"
        self.csp = os.getenv("CSP_POLICY", _DEFAULT_CSP)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if not self.enabled or scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def _send(event):
            if event["type"] == "http.response.start":
                headers = event.setdefault("headers", [])
                def _h(k,v): headers.append((k.encode(), v.encode()))
                _h("content-security-policy", self.csp)
                _h("x-frame-options", "DENY")
                _h("referrer-policy", "no-referrer")
                _h("x-content-type-options", "nosniff")
                _h("strict-transport-security", "max-age=31536000; includeSubDomains")
                _h("permissions-policy", "geolocation=(), microphone=(), camera=()")
            await send(event)
        await self.app(scope, receive, _send)