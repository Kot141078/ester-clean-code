# -*- coding: utf-8 -*-
"""
modules/thinking/role_router.py — marshrutizator roley leader/assistant/observer.

Sostoyanie (v pamyati, s sokhraneniem v fayl):
data/coop/roles.json
{
  "role": "leader",
  "peers": ["127.0.0.1:8000"],
  "policy": {
     "forward": ["missions.step","desktop.window.hotkey"],  # kakie vyzovy retranslirovat na peers
     "observe": true                                        # otpravlyat li overleynye PNG nablyudatelyam
  }
}

API:
- set_role(role), add_peer(host), drop_peer(host), status()
- forward_call(tag, path, payload) -> lokalno + na peers (esli policy razreshaet)
- ESTER_ROLE_ROUTER_URL задает peer по умолчанию (default: http://127.0.0.1:8000)

MOSTY:
- Yavnyy: (Orkestratsiya ↔ Set) kto vedet, kto pomogaet, kto nablyudaet — formalno.
- Skrytyy #1: (Infoteoriya ↔ Bezopasnost) whitelists dlya peresylki tolko razreshennykh deystviy.
- Skrytyy #2: (Memory ↔ Volya) sostoyanie roli vliyaet na povedenie vsekh RPA/missiy.

ZEMNOY ABZATs:
Bez brokerov: obychnye HTTP-vyzovy na peers cherez suschestvuyuschiy peer-proksi.

# c=a+b
"""
from __future__ import annotations
import os, json
from typing import Dict, Any, List
from urllib.parse import urlparse

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR = os.path.join(ROOT, "data", "coop")
FILE = os.path.join(DIR, "roles.json")

def _normalize_peer(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        return raw
    parsed = urlparse(raw)
    if not parsed.hostname:
        return ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"{parsed.hostname}:{port}"

def _default_peers() -> List[str]:
    raw = (os.getenv("ESTER_ROLE_ROUTER_URL") or "http://127.0.0.1:8000").strip()
    normalized = _normalize_peer(raw)
    return [normalized] if normalized else []

_DEF = {
    "role": "leader",
    "peers": _default_peers(),
    "policy": {"forward": ["missions.step", "desktop.window.hotkey"], "observe": True},
}

def _load() -> Dict[str, Any]:
    os.makedirs(DIR, exist_ok=True)
    if not os.path.exists(FILE):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(_DEF, f, ensure_ascii=False, indent=2)
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(obj: Dict[str, Any]) -> None:
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def set_role(role: str) -> Dict[str, Any]:
    obj = _load(); role = (role or "leader").lower()
    if role not in ("leader","assistant","observer"): return {"ok": False, "error": "bad_role"}
    obj["role"] = role; _save(obj)
    return {"ok": True, "role": role}

def add_peer(host: str) -> Dict[str, Any]:
    obj = _load()
    host = _normalize_peer(host)
    if not host: return {"ok": False, "error":"host_required"}
    if host not in obj["peers"]: obj["peers"].append(host); _save(obj)
    return {"ok": True, "peers": obj["peers"]}

def drop_peer(host: str) -> Dict[str, Any]:
    obj = _load(); obj["peers"] = [p for p in obj["peers"] if p != host]; _save(obj)
    return {"ok": True, "peers": obj["peers"]}

def status() -> Dict[str, Any]:
    return _load()

# Simple forwarder: will return the peer's response sheet (the local response does not execute here - the calling handle does this)
import http.client, json as _json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def forward_call(tag: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    st = _load()
    if tag not in st.get("policy", {}).get("forward", []):
        return {"ok": True, "skipped": True, "reason": "not_in_whitelist"}
    results = []
    for host in st.get("peers", []):
        # through an existing proxy peer
        try:
            conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
            body = _json.dumps({"host": host, "path": path, "payload": payload})
            conn.request("POST", "/peer/proxy", body=body, headers={"Content-Type":"application/json"})
            r = conn.getresponse()
            t = r.read().decode("utf-8","ignore"); conn.close()
            try: results.append(_json.loads(t))
            except Exception: results.append({"ok": False, "raw": t})
        except Exception as e:
            results.append({"ok": False, "error": str(e)})
    return {"ok": True, "peers": results}
