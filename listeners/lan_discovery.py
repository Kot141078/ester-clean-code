# -*- coding: utf-8 -*-
"""
listeners/lan_discovery.py — UDP-multicast «mayak» + priemnik + obmen profileami.

Protokol (JSON, UTF-8, 1 paket):
  { "t": "hello"|"req"|"passport", "ts": <unix>, "node": {"id","name"}, "port": <udp_port>, "sig": "<hex>", "payload": {...} }

Povedenie:
  • Periodicheski shlem "hello" v gruppu (model Ashbi: nablyudaemost).
  • Prinimaem pakety, vedem peers-tablitsu {ip -> {..., last_seen}} v {STATE}/lan_peers.json.
  • Esli auto_exchange=1:
      - na hello — otpravlyaem "req" adresatu (unicast).
      - na req — otpravlyaem "passport" (v AB=A — ukorochennyy profile).
  • HMAC podpis cherez shared_key; bez klyucha pakety schitayutsya nepodpisannymi (accepted, verified=false).

ENV/CFG: sm. modules.lan.lan_settings.

Mosty:
- Yavnyy (Kibernetika ↔ Nablyudaemost): LAN-mayak daet zhivuyu kartu sosedey.
- Skrytyy 1 (Infoteoriya ↔ Bezopasnost): HMAC-podpis snizhaet risk «shumnykh» uzlov.
- Skrytyy 2 (Praktika ↔ Sovmestimost): drop-in; JSON-format sovmestim s P2P-konvertami po dukhu.

Zemnoy abzats:
Eto «ratsiya dvora»: uzly peregovarivayutsya na obschem kanale, znakomyatsya i pri neobkhodimosti obmenivayutsya vizitkami (profileami).

# c=a+b
"""
from __future__ import annotations

import argparse, json, os, socket, struct, time
from pathlib import Path
from typing import Any, Dict

from modules.lan.lan_settings import load_settings  # type: ignore
from modules.lan.lan_crypto import sign, verify  # type: ignore
from modules.selfmanage.node_inventory import passport  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AB_MODE") or "A").strip().upper()
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
PEERS = STATE_DIR / "lan_peers.json"

def _load_peers() -> Dict[str, Any]:
    try:
        if PEERS.exists():
            return json.loads(PEERS.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"peers": {}}

def _save_peers(d: Dict[str, Any]) -> None:
    try:
        PEERS.parent.mkdir(parents=True, exist_ok=True)
        PEERS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _node_id() -> str:
    try:
        import platform
        return platform.node() or socket.gethostname()
    except Exception:
        return socket.gethostname()

def _shorten_passport(p: Dict[str, Any], limit: int) -> Dict[str, Any]:
    # Urezaem «tyazhelye» polya, chtoby vlezlo v MTU.
    out = json.loads(json.dumps(p))  # deepcopy
    inv = out.get("inventory", {})
    # obrezaem spiski
    inv["disks"] = []
    rt = inv.get("runtimes", {})
    for k in ("lmstudio","ollama"):
        if isinstance(rt.get(k), dict):
            rt[k]["models"] = []
    out["inventory"] = inv
    txt = json.dumps(out, ensure_ascii=False)
    if len(txt.encode("utf-8")) <= limit:
        return out
    # esli vse esche velik — ostavim tolko zagolovok
    return {
        "kind": out.get("kind","ester-node-passport"),
        "version": out.get("version",1),
        "ts": out.get("ts"),
        "inventory": {
            "node": inv.get("node"),
            "ab_mode": inv.get("ab_mode"),
            "os": inv.get("os"),
            "cpu": inv.get("cpu"),
            "ram_gb": inv.get("ram_gb"),
            "gpus": [],
            "runtimes": {},
            "ts": inv.get("ts"),
            "notes": "short",
        }
    }

def _mk_sock(group: str, port: int) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception:
        pass
    s.bind(("", port))
    mreq = struct.pack("=4sl", socket.inet_aton(group), socket.INADDR_ANY)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    # TTL=1 (lokalnaya set)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    s.settimeout(0.5)
    return s

def _sendto(s: socket.socket, data: Dict[str, Any], addr: Any, key: str) -> None:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    data["sig"] = sign(raw, key) if key else ""
    pkt = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    s.sendto(pkt, addr)

def _handle_packet(pkt: bytes, src: Any, cfg: Dict[str, Any], peers: Dict[str, Any]) -> None:
    ip, _ = src
    try:
        data = json.loads(pkt.decode("utf-8", errors="ignore"))
    except Exception:
        return
    sig = data.get("sig") or ""
    tmp = dict(data); tmp.pop("sig", None)
    raw = json.dumps(tmp, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    verified = verify(raw, sig, cfg.get("shared_key",""))

    t = str(data.get("t") or "")
    node = (data.get("node") or {})
    nid = str(node.get("id") or ip)
    name = str(node.get("name") or "?")
    ts = int(data.get("ts") or int(time.time()))
    port = int(data.get("port") or cfg["port"])

    rec = peers.setdefault("peers", {}).setdefault(ip, {})
    rec.update({"id": nid, "name": name, "last_seen": ts, "verified": bool(verified), "port": port, "last_t": t})
    _save_peers(peers)

    # Avtoobmen
    if not cfg.get("auto_exchange", True):
        return

    # Zapros profilea na hello
    if t == "hello":
        # otvetim individualnym req
        req = {"t":"req", "ts":int(time.time()), "node":{"id":_node_id(),"name":_node_id()}, "port": cfg["port"], "payload":{}}
        _sendto(_SOCK, req, (ip, port), cfg.get("shared_key",""))
        return

    # Na req — otpravim profile (v A — ukorochennyy)
    if t == "req":
        p = passport()
        limit = int(cfg.get("max_packet", 1400)) - 128  # zapas na zagolovki
        if AB != "B":
            p = _shorten_passport(p, limit)
        # Obrezka na vsyakiy sluchay
        txt = json.dumps(p, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(txt) > limit:
            p = _shorten_passport(p, limit)
        rep = {"t":"passport","ts":int(time.time()),"node":{"id":_node_id(),"name":_node_id()}, "port": cfg["port"], "payload": p}
        _sendto(_SOCK, rep, (ip, port), cfg.get("shared_key",""))
        return

    # Na passport — prosto otmetim v peers poslednyuyu kopiyu (bez zapisi na disk konfigov)
    if t == "passport":
        rec["last_passport_ts"] = ts
        rec["has_passport"] = True
        # Ne sokhranyaem payload — chtoby ne plodit personalnye dannye na disk.
        _save_peers(peers)

# Globalnaya ssylka na soket — uproschaet otvety
_SOCK: socket.socket

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester LAN discovery")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=0)
    args = ap.parse_args(argv)

    cfg = load_settings()
    if not cfg.get("enable"):
        print("[lan] disabled", flush=True); return 0

    interval = int(args.interval or cfg.get("interval", 15))
    group, port = cfg.get("group","239.255.43.21"), int(cfg.get("port",54545))

    global _SOCK
    _SOCK = _mk_sock(group, port)

    last_hello = 0
    peers = _load_peers()

    try:
        while True:
            now = time.time()
            if now - last_hello >= max(3, interval):
                hello = {
                    "t":"hello", "ts":int(now),
                    "node":{"id":_node_id(), "name":_node_id()},
                    "port": port,
                    "payload":{"ab": AB, "v":1}
                }
                _sendto(_SOCK, hello, (group, port), cfg.get("shared_key",""))
                last_hello = now

            try:
                pkt, src = _SOCK.recvfrom(65535)
            except socket.timeout:
                pkt = None
            if pkt:
                # ne reagiruem na svoe (grubaya proverka po imeni/ID)
                try:
                    j = json.loads(pkt.decode("utf-8", errors="ignore"))
                    if (j.get("node") or {}).get("id") == _node_id():
                        pass  # propustim; vse ravno obnovim peers dlya vidimosti
                except Exception:
                    pass
                _handle_packet(pkt, src, cfg, peers)

            if not args.loop:
                break
    except KeyboardInterrupt:
        pass
    finally:
        try:
            _SOCK.close()
        except Exception:
            pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b