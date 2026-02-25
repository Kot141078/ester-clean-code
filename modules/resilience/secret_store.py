# -*- coding: utf-8 -*-
"""modules/resilience/secret_store.py - lokalnyy sekret-stor: put/get/list/rotate s auto encrypted.

Mosty:
- Yavnyy: (Sekrety ↔ Kod) edinyy sposob khranit API-klyuchi/tokeny bez ENV-utechek.
- Skrytyy #1: (Infoteoriya ↔ Audit) metadannye/vremena/versii, JSON-reestr.
- Skrytyy #2: (Kibernetika ↔ Vyzhivanie) rotatsiya i minimum otkazov (NaCl pri nalichii, XOR-potok kak follbek).

Zemnoy abzats:
This is “zapisnaya knizhka v seyfe”: polozhit/vzyat sekret, pri zhelanii smenit zamok.

# c=a+b"""
from __future__ import annotations
import os, json, base64, time, hashlib
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DIR = os.getenv("SECRETS_DIR","data/secrets")
MASTER = os.getenv("SECRETS_MASTER","data/secrets/master.key")
ALG = os.getenv("SECRETS_ALG","auto")

try:
    from nacl.secret import SecretBox  # type: ignore
    from nacl.utils import random as nacl_random  # type: ignore
    HAS_NACL = True
except Exception:
    HAS_NACL = False

def _ensure():
    os.makedirs(DIR, exist_ok=True)
    if not os.path.isfile(MASTER):
        key = os.urandom(32)
        open(MASTER,"wb").write(key)
        try: os.chmod(MASTER, 0o600)
        except Exception: pass

def _mkbox():
    _ensure()
    key = open(MASTER,"rb").read()
    if ALG=="nacl" or (ALG=="auto" and HAS_NACL):
        return ("nacl", SecretBox(key[:32]) if HAS_NACL else None, key)
    return ("xor", None, key)

def _enc(data: bytes) -> Dict[str,str]:
    alg, box, key = _mkbox()
    if alg=="nacl" and box:
        nonce = nacl_random(24)
        ct = box.encrypt(data, nonce)
        return {"alg":"nacl","blob": base64.b64encode(ct).decode("ascii")}
    # XOR potok (psevdo): HKDF-like derivatsiya iz sha256(key||nonce)
    nonce = os.urandom(16)
    stream = hashlib.sha256(key + nonce).digest()
    out = bytes([b ^ stream[i % len(stream)] for i,b in enumerate(data)])
    return {"alg":"xor","nonce": base64.b64encode(nonce).decode("ascii"), "blob": base64.b64encode(out).decode("ascii")}

def _dec(obj: Dict[str,str]) -> bytes:
    alg, box, key = _mkbox()
    if obj.get("alg")=="nacl" and HAS_NACL and box:
        return box.decrypt(base64.b64decode(obj["blob"]))
    nonce = base64.b64decode(obj.get("nonce","")) if obj.get("nonce") else b"\x00"*16
    stream = hashlib.sha256(key + nonce).digest()
    raw = base64.b64decode(obj["blob"])
    return bytes([b ^ stream[i % len(stream)] for i,b in enumerate(raw)])

def put(name: str, value: str) -> Dict[str, Any]:
    _ensure()
    path = os.path.join(DIR, f"{name}.sec.json")
    obj = {"v":1,"enc":_enc(value.encode("utf-8")),"ts":int(time.time())}
    json.dump(obj, open(path,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    try: os.chmod(path, 0o600)
    except Exception: pass
    return {"ok": True, "name": name}

def get(name: str) -> Dict[str, Any]:
    path = os.path.join(DIR, f"{name}.sec.json")
    if not os.path.isfile(path): return {"ok": False, "error":"not_found"}
    obj = json.load(open(path,"r",encoding="utf-8"))
    try:
        raw = _dec(obj.get("enc") or {})
        return {"ok": True, "name": name, "value": raw.decode("utf-8", errors="ignore")}
    except Exception as e:
        return {"ok": False, "error": f"decrypt_failed:{e}"}

def rotate() -> Dict[str, Any]:
    """Generates a new master key and re-encrypts all secrets."""
    _ensure()
    old = open(MASTER,"rb").read()
    new = os.urandom(32)
    open(MASTER,"wb").write(new)
    # peresokhranenie sekretov
    rep=[]
    for fn in os.listdir(DIR):
        if not fn.endswith(".sec.json"): continue
        p = os.path.join(DIR, fn)
        obj = json.load(open(p,"r",encoding="utf-8"))
        # temporarily replace MASTER with the old one to decrypt
        open(MASTER,"wb").write(old)
        val = _dec(obj.get("enc") or {})
        # return the new key and resave
        open(MASTER,"wb").write(new)
        json.dump({"v":1,"enc":_enc(val),"ts":int(time.time())}, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
        rep.append(fn)
    try: os.chmod(MASTER, 0o600)
    except Exception: pass
    return {"ok": True, "rotated": len(rep)}
# c=a+b