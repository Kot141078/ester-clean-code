# -*- coding: utf-8 -*-
"""
listeners/lan_catalog_service.py — LAN Catalog Service:
  • UDP-anons (multicast/broadcast) «ya tut»
  • priem chuzhikh anonsov → kesh → HTTP GET /lan/catalog_export u soseda → kesh kataloga

ENV:
  LAN_CATALOG_ENABLE=1
  LAN_CATALOG_GROUP=239.23.0.73
  LAN_CATALOG_PORT=40730
  LAN_CATALOG_ANNOUNCE_SEC=30
  LAN_CATALOG_PULL_SEC=60
  LAN_CATALOG_NODE_NAME=EsterNode
  LAN_CATALOG_BASE_URL=http://127.0.0.1:8000

Zemnoy abzats:
Legkiy «mayak»: periodicheski govorit «ya zdes, vot moy URL», i podbiraet chuzhie katalogi dlya adminki.

Mosty:
- Yavnyy (Set ↔ Katalogi): UDP-mayak ↔ HTTP-katalog.
- Skrytyy 1 (Infoteoriya): formaty beacon/catalog prosty i proveryaemy.
- Skrytyy 2 (Praktika): stdlib sockets/urllib, offlayn (tolko LAN).

# c=a+b
"""
from __future__ import annotations
import argparse, json, os, socket, struct, threading, time, urllib.request, urllib.error

from modules.lan_catalog.exporter import build_local_catalog  # type: ignore
from modules.lan_catalog.peers import save_beacon, save_catalog  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _env(name: str, default: str) -> str:
    return (os.getenv(name) or default)

def _beacon() -> dict:
    return {
        "schema": "ester.lan.beacon/1",
        "node": _env("LAN_CATALOG_NODE_NAME","EsterNode"),
        "base_url": _env("LAN_CATALOG_BASE_URL","http://127.0.0.1:8000").rstrip("/"),
        "ts": int(time.time())
    }

def _send_udp(sock, addr):
    msg = json.dumps(_beacon()).encode("utf-8")
    try:
        sock.sendto(msg, addr)
    except Exception:
        pass

def _make_mcast_sender(group: str, port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        addr = (group, port)
        return sock, addr
    except Exception:
        sock.close()
        # fallback broadcast
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        return sock, ("255.255.255.255", port)

def _make_mcast_receiver(group: str, port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception:
        pass
    try:
        sock.bind(("", port))
        mreq = struct.pack("=4sl", socket.inet_aton(group), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        return sock
    except Exception:
        # fallback: prosto slushaem broadcast na portu
        sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", port))
        return sock

def _pull_catalog(base_url: str):
    url = base_url.rstrip("/") + "/lan/catalog_export"
    try:
        with urllib.request.urlopen(url, timeout=2.5) as r:
            if r.status == 200:
                data = json.loads(r.read().decode("utf-8"))
                node = data.get("node") or base_url
                save_catalog(node, data)
    except Exception:
        pass

def run_loop():
    if (os.getenv("LAN_CATALOG_ENABLE","1") != "1"):
        print(json.dumps({"mod":"lan_catalog_service","status":"disabled"}), flush=True)
        return
    group = _env("LAN_CATALOG_GROUP","239.23.0.73")
    port  = int(_env("LAN_CATALOG_PORT","40730"))
    ann_sec = int(_env("LAN_CATALOG_ANNOUNCE_SEC","30"))
    pull_sec = int(_env("LAN_CATALOG_PULL_SEC","60"))

    snd_sock, snd_addr = _make_mcast_sender(group, port)
    rcv_sock = _make_mcast_receiver(group, port)

    last_ann = 0
    last_pull = 0
    my_base = _env("LAN_CATALOG_BASE_URL","http://127.0.0.1:8000").rstrip("/")
    try:
        while True:
            now = time.time()
            # periodicheskiy anons
            if now - last_ann >= ann_sec:
                _send_udp(snd_sock, snd_addr)
                last_ann = now
            # priem
            rcv_sock.settimeout(0.5)
            try:
                data, addr = rcv_sock.recvfrom(64*1024)
                try:
                    obj = json.loads(data.decode("utf-8"))
                except Exception:
                    obj = {}
                if obj.get("schema") == "ester.lan.beacon/1":
                    base = (obj.get("base_url") or "").rstrip("/")
                    if base and base != my_base:
                        save_beacon(obj)
                # periodicheski tyanem katalogi vsekh izvestnykh
            except socket.timeout:
                pass

            if now - last_pull >= pull_sec:
                # perechen izvestnykh
                try:
                    from modules.lan_catalog.peers import list_peers  # lazy
                    peers = list_peers().get("peers") or []
                    for p in peers:
                        base = (p.get("base_url") or "").rstrip("/")
                        if base and base != my_base:
                            _pull_catalog(base)
                except Exception:
                    pass
                last_pull = now
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        try: snd_sock.close()
        except Exception: pass
        try: rcv_sock.close()
        except Exception: pass

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester LAN Catalog Service")
    ap.add_argument("--loop", action="store_true")
    args = ap.parse_args(argv)
    run_loop()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b