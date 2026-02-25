# -*- coding: utf-8 -*-
"""modules/trust/sign.py - lokalnye podpisi artefaktov (HMAC-SHA256) i proverka.

Mosty:
- Yavnyy: (Bezopasnost ↔ Tselostnost) podpisyvaem fayly/manifesty i proveryaem pered zapuskom.
- Skrytyy #1: (Infoteoriya ↔ Audit) signatury sokhranyayutsya v .sig.json ryadom s faylom.
- Skrytyy #2: (Avtonomiya ↔ Samosborka) relizy soderzhat manifest s podpisyami.

Zemnoy abzats:
Kak pechat na konverte - bez pravilnoy “mastiki” fayl ne primem.

# c=a+b"""
from __future__ import annotations
import os, json, hmac, hashlib, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DIR  = os.getenv("TRUST_DIR","data/trust")
KEYF = os.getenv("TRUST_KEY_FILE","data/trust/hmac_key.json")

def _ensure():
    os.makedirs(DIR, exist_ok=True)

def key_status() -> Dict[str,Any]:
    _ensure()
    if not os.path.isfile(KEYF):
        return {"ok": True, "exists": False}
    j=json.load(open(KEYF,"r",encoding="utf-8"))
    return {"ok": True, "exists": True, "kid": j.get("kid"), "created": j.get("ts")}

def key_init() -> Dict[str,Any]:
    _ensure()
    if os.path.isfile(KEYF):
        return {"ok": False, "error":"key_exists"}
    import secrets
    key = secrets.token_bytes(32)
    kid = hashlib.sha256(key).hexdigest()[:16]
    json.dump({"kid": kid, "key": key.hex(), "ts": int(time.time())}, open(KEYF,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "kid": kid}

def _load_key() -> bytes:
    j=json.load(open(KEYF,"r",encoding="utf-8"))
    return bytes.fromhex(j.get("key"))

def sign_path(path: str) -> Dict[str,Any]:
    if not os.path.isfile(KEYF):
        return {"ok": False, "error":"no_key"}
    if not os.path.isfile(path):
        return {"ok": False, "error":"not_found"}
    k=_load_key()
    data=open(path,"rb").read()
    sha=hashlib.sha256(data).hexdigest()
    mac=hmac.new(k, data, hashlib.sha256).hexdigest()
    sig={"path": os.path.abspath(path), "sha256": sha, "algo":"HMAC-SHA256", "kid": key_status().get("kid"), "sig": mac, "ts": int(time.time())}
    json.dump(sig, open(path+".sig.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, **sig}

def verify_sig(sig: Dict[str,Any]) -> Dict[str,Any]:
    path=sig.get("path","")
    if not os.path.isfile(path): return {"ok": False, "error":"not_found"}
    if not os.path.isfile(KEYF): return {"ok": False, "error":"no_key"}
    k=_load_key()
    data=open(path,"rb").read()
    mac=hmac.new(k, data, hashlib.sha256).hexdigest()
    sha=hashlib.sha256(data).hexdigest()
    return {"ok": (mac==sig.get("sig") and sha==sig.get("sha256")), "calc_sha256": sha}
# c=a+b