# -*- coding: utf-8 -*-
"""Prostoy LAN-peer: obyavlyaet Ester po mDNS i slushaet sosedey.
Publikuem _ester._tcp.local na zadannom portu, sobiraem peer-list i pechataem JSON-slepki raz v 10s.
"""
from __future__ import annotations

import json
import socket
import time

from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SERVICE_TYPE = "_ester._tcp.local."


class PeerListener:
    def __init__(self):
        self.peers = {}

    def add_service(self, zc, t, name):
        info = zc.get_service_info(t, name)
        if info:
            host = socket.inet_ntoa(info.addresses[0]) if info.addresses else None
            props = {}
            for k, v in (info.properties or {}).items():
                try:
                    props[k.decode()] = v.decode()
                except Exception:
                    props[str(k)] = str(v)
            self.peers[name] = {"host": host, "port": info.port, "props": props}

    def remove_service(self, zc, t, name):
        self.peers.pop(name, None)


def main(host: str = "0.0.0.0", port: int = 5000, name: str = "ester-peer"):
    zc = Zeroconf()
    desc = {"ver": "1", "ts": str(int(time.time()))}
    info = ServiceInfo(
        SERVICE_TYPE,
        f"{name}.{SERVICE_TYPE}",
        addresses=[socket.inet_aton(socket.gethostbyname(socket.gethostname()))],
        port=port,
        properties=desc,
    )
    zc.register_service(info)
    listener = PeerListener()
    browser = ServiceBrowser(zc, SERVICE_TYPE, listener)

    try:
        while True:
            print(
                json.dumps(
                    {"ts": int(time.time()), "peers": listener.peers},
                    ensure_ascii=False,
                )
            )
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        zc.unregister_service(info)
        zc.close()


if __name__ == "__main__":
    import os

    main(
        port=int(os.getenv("ESTER_PORT", "5000")),
        name=os.getenv("ESTER_PEER_NAME", "ester-peer"),
    )
