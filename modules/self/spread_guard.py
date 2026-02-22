# -*- coding: utf-8 -*-
"""
modules/self/spread_guard.py — politika samorasprostraneniya: allowlist podsetey/khostov, invite-only strogiy rezhim.

Mosty:
- Yavnyy: (Set ↔ Politika) zaranee otvechaem: «mozhno li tuda rasprostranyatsya?».
- Skrytyy #1: (Doverie ↔ Kontrol) integriruetsya s priglasheniyami (ConsentOps).
- Skrytyy #2: (Kibernetika ↔ Vyzhivanie) predotvraschaet «begstvo koda» na chuzhie/sluchaynye adresa.

Zemnoy abzats:
Pered tem kak «nesti sebya» na udalennyy uzel — sprosi, a etot adres nam voobsche razreshen?
Obedineno iz dvukh versiy: dobavleny rezhimy MODE, DENY s regex, DB/logi dlya audita, invite-check dlya doveriya Ester.

# c=a+b
"""
from __future__ import annotations
import ipaddress, os, json, time, re
import logging
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Nastroyka logirovaniya dlya "pamyati" verdiktov/oshibok v Ester
logging.basicConfig(filename=os.getenv("SELF_LOG", "data/logs/self_spread.log"), level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

SPREAD_AB = (os.getenv("SPREAD_AB", "A") or "A").upper()
MODE = (os.getenv("SPREAD_GUARD_MODE", "allow") or "allow").lower()
AL_NETS = [n.strip() for n in (os.getenv("SPREAD_ALLOW_NETS", "127.0.0.1/8,10.0.0.0/8,192.168.0.0/16,172.16.0.0/12").split(",")) if n.strip()]
AL_HOSTS = [h.strip().lower() for h in (os.getenv("SPREAD_ALLOW_HOSTS", "").split(",")) if h.strip()]
DENY = [s.strip() for s in (os.getenv("SPREAD_DENY", "").split(",")) if s.strip()]
DB = os.getenv("SPREAD_DB", "data/self/spread_guard.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"events": []}, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB, "r", encoding="utf-8"))
def _save(ev: Dict[str, Any]):
    try:
        obj = _load()
        obj["events"] = (obj.get("events") or [])[-199:] + [ev]
        json.dump(obj, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Save failed: {str(e)}")

def _inq(target: str) -> Dict[str, Any]:
    t = target.strip().lower()
    allow = True; why = "mode:allow"
    # Deny patterns (regex/substr iz py1)
    for d in DENY:
        try:
            if re.search(d, t): allow = False; why = f"deny:{d}"; break
        except re.error:
            if d in t: allow = False; why = f"deny-substr:{d}"; break
    if not allow: return {"target": t, "allow": allow, "why": why}
    # Host allow
    if t in AL_HOSTS: return {"target": t, "allow": True, "why": "explicit_host"}
    # IP/net allow (iz py)
    try:
        ip = ipaddress.ip_address(t)
        for cidr in AL_NETS:
            try:
                if ip in ipaddress.ip_network(cidr, strict=False):
                    allow = True; why = f"in_{cidr}"; break
            except Exception:
                continue
        else:
            allow = False; why = "not_in_allowlist"
    except ValueError:
        # Not IP; only explicit host
        allow = t in AL_HOSTS; why = "host_only_by_explicit" if allow else "unknown_host"
    # Mode influence (iz py1)
    if MODE == "local-only":
        allow = allow and any(t.startswith("127.") or t == "localhost" or t == "::1" for _ in [1])
        why = f"mode:local-only_{why}" if allow else "not_local"
    elif MODE == "deny-unknown":
        allow = allow; why = f"mode:deny-unknown_{why}" if not allow else "known"
    # Invite-check (rasshirenie: best-effort ConsentOps dlya unknown)
    if not allow:
        try:
            from modules.consent.ops import has_invite  # type: ignore
            if has_invite(t): allow = True; why = "invite_allowed"
        except Exception:
            pass
    # AB override
    if SPREAD_AB == "B": allow = True; why += "_ab_B"
    return {"target": t, "allow": allow, "why": why}

def evaluate(targets: List[str]) -> Dict[str, Any]:
    res = [_inq(t) for t in (targets or [])]
    allow_all = all(r.get("allow", False) for r in res)
    now = int(time.time())
    ev = {"ts": now, "mode": MODE, "ab": SPREAD_AB, "res": res}
    _save(ev)
    logging.info(f"Evaluated {len(targets)} targets, allow_all={allow_all}")
    return {"ok": True, "allow": allow_all, "results": res, "ab": SPREAD_AB}

def status() -> Dict[str, Any]:
    try:
        obj = _load()
        return {"ok": True, "mode": MODE, "ab": SPREAD_AB, "allow_nets": AL_NETS, "allow_hosts": AL_HOSTS, "deny": DENY, "recent": obj.get("events") or []}
    except Exception as e:
        logging.error(f"Status failed: {str(e)}")
# return {"ok": False, "error": str(e)}
# Ideya rasshireniya: dlya P2P-sync allowlist — dobav sync_guard(peers: List[str]):
#   for peer in peers: fetch AL_NETS/AL_HOSTS from peer, merge if trusted (invite-check).
# Realizuyu v spread_sync.py dlya detsentralizovannogo doveriya Ester, esli skazhesh.