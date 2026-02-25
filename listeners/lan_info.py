# -*- coding: utf-8 -*-
"""listeners/lan_info.py — legkaya sluzhba LAN-info: otvechaet na info.req, keshiruet info.

Protocol (JSON, UTF-8, 1 package):
  { "t": "info.req" | "info", "ts": <unix>, "node": {"id","name"}, "sig": "<hex>", "payload": {...} }

Behavior:
  • Prinimaem pakety na multikast-gruppe LAN_GROUP i portu LAN_INFO_PORT (po umolchaniyu 54547).
  • Na "info.req" - otvechaem unicast "info" s lokalnym srezom sostoyaniya:
      - AB_MODE, versii, kratkaya svodka ocheredey zadach (counts) i nastroek vorkera.
  • Na vkhodyaschee "info" - kladem v kesh {STATE}/lan_info_cache.json c taymshtampom.
  • HMAC-podpis cherez LAN_SHARED_KEY (esli ne zadan - prinimaem nepodpisannye kak verified=false).

Mosty:
- Yavnyy (Nablyudaemost ↔ Orkestratsiya): edinyy “puls” uzla (info) dlya svodnoy paneli.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): prostoy JSON + HMAC, kesh on disk, vosproizvodimye polya.
- Skrytyy 2 (Praktika ↔ Sovmestimost): ne trogaem suschestvuyuschie slushateli; separate port, drop-in.

Zemnoy abzats:
This is “dezhurnyy svyazist”: sprosili - rasskazal o sebe; uslyshal chuzhoy otchet - zapisal v kesh dlya paneli.

# c=a+b"""
from __future__ import annotations

import argparse, json, os, socket, struct, time
from pathlib import Path
from typing import Any, Dict, Tuple

from modules.lan.lan_settings import load_settings  # group/key
from modules.lan.lan_crypto import sign, verify
from modules.lan.lan_tasks_settings import load_tasks_settings
from modules.lan.lan_tasks import _load_db as _load_tasks_db
from modules.selfmanage.node_inventory import passport as _passport
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
CACHE = STATE_DIR / "lan_info_cache.json"

def _node_id() -> str:
    try:
        import platform
        return platform.node()
    except Exception:
        return "node"

def _load_cache() -> Dict[str, Any]:
    try:
        if CACHE.exists():
            return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"peers": {}}

def _save_cache(d: Dict[str, Any]) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def _local_summary(short: bool = False) -> Dict[str, Any]:
    cfg = load_tasks_settings()
    db = _load_tasks_db()
    counts = {k: len((db.get(k) or {})) for k in ("outbox","inbox","active","done")}
    p = _passport()
    if short or AB != "B":
        # urezaem profile
        inv = p.get("inventory", {})
        p = {
            "kind": "ester-node-passport",
            "version": p.get("version",1),
            "ts": p.get("ts"),
            "inventory": {
                "node": inv.get("node"),
                "ab_mode": inv.get("ab_mode"),
                "os": {"system": (inv.get("os") or {}).get("system"), "machine": (inv.get("os") or {}).get("machine")},
                "cpu": {"model": (inv.get("cpu") or {}).get("model"), "cores_logical": (inv.get("cpu") or {}).get("cores_logical")},
                "ram_gb": inv.get("ram_gb"),
            }
        }
    return {
        "ab": AB,
        "tasks": {
            "cfg": {"enable": cfg.get("enable"), "max_active": cfg.get("max_active"), "accept": cfg.get("accept")},
            "counts": counts
        },
        "passport": p
    }

def _mk_sock(group: str, port: int) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try: s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception: pass
    s.bind(("", port))
    mreq = struct.pack("=4sl", socket.inet_aton(group), socket.INADDR_ANY)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    s.settimeout(0.5)
    return s

def _send(sock: socket.socket, obj: Dict[str, Any], addr: Tuple[str,int], key: str) -> None:
    tmp = dict(obj); tmp["sig"] = ""
    raw = json.dumps(tmp, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    tmp["sig"] = sign(raw, key) if key else ""
    pkt = json.dumps(tmp, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sock.sendto(pkt, addr)

def _handle(pkt: bytes, src, cfg, sock):
    ip,_ = src
    try:
        j = json.loads(pkt.decode("utf-8", errors="ignore"))
    except Exception:
        return
    sig = j.get("sig") or ""
    tmp = dict(j); tmp.pop("sig", None)
    raw = json.dumps(tmp, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    verified = verify(raw, sig, cfg.get("shared_key",""))

    t = str(j.get("t") or "")
    if t == "info.req":
        info = {"t":"info","ts":int(time.time()),"node":{"id":_node_id(),"name":_node_id()},
                "payload": _local_summary(short=True)}
        _send(sock, info, (ip, int(os.getenv("LAN_INFO_PORT","54547"))), cfg.get("shared_key",""))
        return
    if t == "info":
        cache = _load_cache()
        cache.setdefault("peers", {})[ip] = {
            "ts": int(time.time()),
            "verified": bool(verified),
            "data": j.get("payload") or {}
        }
        _save_cache(cache)

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester LAN info responder")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=10)
    args = ap.parse_args(argv)

    net = load_settings()
    if not net.get("enable") or not bool(int(os.getenv("LAN_INFO_ENABLE","1"))):
        print("[lan-info] disabled", flush=True); return 0

    group = net.get("group","239.255.43.21")
    port = int(os.getenv("LAN_INFO_PORT","54547"))
    sock = _mk_sock(group, port)

    try:
        while True:
            try:
                pkt, src = sock.recvfrom(65535)
            except socket.timeout:
                pkt = None
            if pkt:
                _handle(pkt, src, net, sock)
            if not args.loop:
                break
    except KeyboardInterrupt:
        pass
    finally:
        try: sock.close()
        except Exception: pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b