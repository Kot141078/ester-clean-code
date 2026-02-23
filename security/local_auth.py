# -*- coding: utf-8 -*-
"""
security/local_auth.py — oflayn-autentifikatsiya i vypusk HS256 JWT dlya roli 'operator'.

Khranenie sekreta/khesha parolya:
  data/security/auth.json
    {
      "salt": "<base64>",
      "pwd_hash": "<hex sha256>",
      "jwt_secret": "<base64>"
    }

Algoritmy: SHA-256 (parol+salt), HS256 (JWT). Bez vneshnikh zavisimostey.

MOSTY:
- Yavnyy: (Bezopasnost ↔ UX) lokalnaya vydacha tokenov dlya UI-pultov /desktop/rpa/* i /vm/*.
- Skrytyy #1: (Infoteoriya ↔ Riski) minimalnyy alfavit roley i prostaya kriptoskhema umenshayut poverkhnost oshibok.
- Skrytyy #2: (Kibernetika ↔ Audit) vkhod/deystviya → edinyy zhurnal: kto i kogda zapuskal stsenarii.

ZEMNOY ABZATs:
Polnostyu oflayn: fayl s solenym kheshem i sekretom dlya JWT, ne trebuet seti/BD. Podderzhivaet rotatsiyu sekreta.

# c=a+b
"""
from __future__ import annotations
import os, json, hmac, hashlib, base64, time
from typing import Tuple, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PROJECT_ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
SEC_DIR = os.path.join(PROJECT_ROOT, "data", "security")
AUTH_PATH = os.path.join(SEC_DIR, "auth.json")

def _ensure_dir() -> None:
    os.makedirs(SEC_DIR, exist_ok=True)

def _rand(n: int = 32) -> bytes:
    return os.urandom(n)

def _b64(x: bytes) -> str:
    return base64.urlsafe_b64encode(x).decode("ascii").rstrip("=")

def _b64dec(s: str) -> bytes:
    s += "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s.encode("ascii"))

def state_exists() -> bool:
    return os.path.exists(AUTH_PATH)

def init_password(password: str) -> None:
    """Odnorazovaya initsializatsiya/pereustanovka operatora."""
    if not password:
        raise ValueError("empty_password")
    _ensure_dir()
    salt = _rand(16)
    pwd_hash = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
    jwt_secret = _rand(32)
    obj = {
        "salt": _b64(salt),
        "pwd_hash": pwd_hash,
        "jwt_secret": _b64(jwt_secret),
    }
    with open(AUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _load_state() -> Dict[str, Any]:
    if not os.path.exists(AUTH_PATH):
        raise RuntimeError("not_initialized")
    with open(AUTH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def verify_password(password: str) -> bool:
    st = _load_state()
    salt = _b64dec(st["salt"])
    want = st["pwd_hash"]
    got = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(want, got)

def jwt_secret() -> bytes:
    st = _load_state()
    return _b64dec(st["jwt_secret"])

def jwt_encode_hs256(payload: Dict[str, Any], key: bytes) -> str:
    import json as _json
    header = {"alg": "HS256", "typ": "JWT"}
    def enc(x: Dict[str, Any]) -> str:
        s = _json.dumps(x, separators=(",", ":"), ensure_ascii=False)
        return _b64(s.encode("utf-8"))
    h = enc(header)
    p = enc(payload)
    msg = (h + "." + p).encode("ascii")
    sig = hmac.new(key, msg, hashlib.sha256).digest()
    return h + "." + p + "." + _b64(sig)

def issue_jwt(sub: str, roles: list[str], ttl_sec: int = 3600) -> str:
    now = int(time.time())
    payload = {"sub": sub, "roles": roles, "iat": now, "exp": now + ttl_sec}
    return jwt_encode_hs256(payload, jwt_secret())

def rotate_secret() -> None:
    """Rotatsiya JWT sekreta (login trebuetsya zanovo)."""
    st = _load_state()
    st["jwt_secret"] = _b64(_rand(32))
    with open(AUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)