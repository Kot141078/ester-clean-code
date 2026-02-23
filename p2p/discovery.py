# -*- coding: utf-8 -*-
"""Prostoy Discovery: obedinyaem staticheskiy spisok i LAN (zeroconf), esli dostupen.
Vozvraschaem spisok bazovykh URL pirov.
"""
from __future__ import annotations

import os
from typing import List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATIC = [x.strip() for x in os.getenv("ESTER_P2P_STATIC", "").split(",") if x.strip()]

try:
    from zeroconf import ServiceBrowser, Zeroconf

    class _Listener:
        def __init__(self):
            self.urls: List[str] = []

        def add_service(self, zc, t, name):
            info = zc.get_service_info(t, name)
            if info and info.port:
                try:
                    import socket

                    host = socket.inet_ntoa(info.addresses[0]) if info.addresses else None
                    if host:
                        self.urls.append(f"http://{host}:{info.port}")
                except Exception:
                    pass

        def remove_service(self, *a, **kw):
            pass

    def lan_peers() -> List[str]:
        zc = Zeroconf()
        l = _Listener()
        ServiceBrowser(zc, "_ester._tcp.local.", l)
        import time

        time.sleep(1.0)
        zc.close()
        return l.urls

except Exception:

    def lan_peers() -> List[str]:
        return []


def peers() -> List[str]:
    urls = list(STATIC)
    for u in lan_peers():
        if u not in urls:
            urls.append(u)
    return urls
