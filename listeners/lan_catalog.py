# -*- coding: utf-8 -*-
"""listeners/lan_catalog.py - fon: multikast-mayak + priem, TTL-ochistka, ARP-reskany (by intervalu).

Behavior:
  • Kazhdye interval sek: beacon_once() + expire_old().
  • Postoyanno slushaem multicast group:port i ingest_packet().
  • V AB=A/B - odinakovo (eto tolko nablyudenie).

ENV/CFG: sm. modules.lan.catalog_settings.

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): podderzhivaem aktualnyy spisok sosedey bez ruchnogo vmeshatelstva.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): TTL-ochistka i self-pamyat umenshayut “zastoynye zapisi”.
- Skrytyy 2 (Praktika ↔ Sovmestimost): chistyy UDP multikast + JSON, bez vneshnikh bibliotek.

Zemnoy abzats:
Eto “mayak i ushi”: periodicheski podaem golos i slushaem chuzhie - tak Ester vidit, kto ryadom.

# c=a+b"""
from __future__ import annotations
import argparse, os, socket, struct, threading, time

from modules.lan.catalog_settings import load_catalog_settings  # type: ignore
from modules.lan.catalog import beacon_once, ingest_packet, expire_old  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _listener():
    cfg = load_catalog_settings()
    group = cfg["group"]; port = int(cfg["port"])
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", port))
    except Exception:
        return
    mreq = struct.pack("=4sl", socket.inet_aton(group), socket.INADDR_ANY)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    except Exception:
        pass
    while True:
        try:
            data, addr = sock.recvfrom(65535)
            ingest_packet(data, addr, cfg)
        except Exception:
            time.sleep(0.05)

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester LAN catalog listener")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=0)
    args = ap.parse_args(argv)

    cfg = load_catalog_settings()
    if not cfg.get("enable"):
        print("[lan-catalog] disabled", flush=True)
        return 0

    th = threading.Thread(target=_listener, daemon=True)
    th.start()

    iv = int(args.interval or cfg.get("interval", 30))
    try:
        while True:
            beacon_once(cfg)
            expire_old(cfg)
            if not args.loop: break
            time.sleep(max(5, iv))
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b