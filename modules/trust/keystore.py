# -*- coding: utf-8 -*-
"""modules/trust/keystore.py - lokalnaya para klyuchey i podpis/proverka (ed25519 esli dostupno; follbek - HMAC-SHA256).

Mosty:
- Yavnyy: (Kripto ↔ Doverie) edinaya tochka “chem podpisyvaem/proveryaem.”
- Skrytyy #1: (Infoteoriya ↔ Audit) otpechatki i serializatsiya v fayly s pravami 0600.
- Skrytyy #2: (Kibernetika ↔ Vyzhivanie) follbek HMAC pozvolyaet rabotat offlayn bez storonnikh zavisimostey.

Zemnoy abzats:
Esli est Ed25519 - ispolzuem sovremennuyu podpis; esli net - ne lomaemsya, podpisyvaem HMAC, chetko pomechaya algoritm.

# c=a+b"""
from __future__ import annotations
import base64, hashlib, json, os
from typing import Dict, Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TRUST_LOCAL_KEY_PATH = os.getenv("TRUST_LOCAL_KEY_PATH","data/trust/local_ed25519.json")
TRUST_FALLBACK_HMAC_PATH = os.getenv("TRUST_FALLBACK_HMAC_PATH","data/secrets/trust_hmac.key")

try:
    from nacl import signing as _nacl_signing  # type: ignore
    from nacl import encoding as _nacl_encoding  # type: ignore
    HAS_NACL = True
except Exception:
    HAS_NACL = False

def _ensure_dir(p: str):
    d = os.path.dirname(p)
    if d: os.makedirs(d, exist_ok=True)

def _chmod600(p: str):
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass

def get_local_identity() -> Dict[str, Any]:
    """Returns the ZZF0Z or XMAS variant.
    Creates keys when missing."""
    if HAS_NACL:
        if not os.path.isfile(TRUST_LOCAL_KEY_PATH):
            _ensure_dir(TRUST_LOCAL_KEY_PATH)
            sk = _nacl_signing.SigningKey.generate()
            obj = {"alg":"ed25519","seed_b64": base64.b64encode(bytes(sk)).decode("ascii")}
            json.dump(obj, open(TRUST_LOCAL_KEY_PATH,"w",encoding="utf-8"))
            _chmod600(TRUST_LOCAL_KEY_PATH)
        obj = json.load(open(TRUST_LOCAL_KEY_PATH,"r",encoding="utf-8"))
        seed = base64.b64decode(obj["seed_b64"])
        sk = _nacl_signing.SigningKey(seed)
        vk = sk.verify_key
        pub_b64 = vk.encode(_nacl_encoding.Base64Encoder).decode("ascii")
        fp = hashlib.sha256(base64.b64decode(pub_b64)).hexdigest()
        return {"alg":"ed25519","pubkey": pub_b64, "fingerprint": fp}
    # follbek — HMAC
    if not os.path.isfile(TRUST_FALLBACK_HMAC_PATH):
        _ensure_dir(TRUST_FALLBACK_HMAC_PATH)
        key = os.urandom(32)
        open(TRUST_FALLBACK_HMAC_PATH,"wb").write(key)
        _chmod600(TRUST_FALLBACK_HMAC_PATH)
    key = open(TRUST_FALLBACK_HMAC_PATH,"rb").read()
    fp = hashlib.sha256(key).hexdigest()
    pub = base64.b64encode(hashlib.sha256(key).digest()).decode("ascii")  # psevdo-publichnyy identifikator
    return {"alg":"hmac","pubkey": pub, "fingerprint": fp}

def sign_bytes(data: bytes) -> Dict[str, str]:
    if HAS_NACL:
        seed = base64.b64decode(json.load(open(TRUST_LOCAL_KEY_PATH,"r",encoding="utf-8"))["seed_b64"])
        sk = _nacl_signing.SigningKey(seed)
        sig = sk.sign(data).signature
        return {"alg":"ed25519","sig": base64.b64encode(sig).decode("ascii")}
    key = open(TRUST_FALLBACK_HMAC_PATH,"rb").read()
    mac = hashlib.sha256(key + data).hexdigest()
    return {"alg":"hmac","sig": mac}

def verify_bytes(data: bytes, alg: str, signature: str, pubkey_b64: str) -> bool:
    try:
        if alg == "ed25519" and HAS_NACL:
            vk = _nacl_signing.VerifyKey(pubkey_b64, encoder=_nacl_encoding.Base64Encoder)
            vk.verify(data, base64.b64decode(signature))
            return True
        if alg == "hmac":
            # pubkey_b64 - not used (identifier), check with a local key? no - it is impossible to check the HMAS of another node.
            # Therefore, XMAS is only valid for local invitations (aud="local").
            key = open(TRUST_FALLBACK_HMAC_PATH,"rb").read()
            mac = hashlib.sha256(key + data).hexdigest()
            return mac == signature
    except Exception:
        return False
    return False
# c=a+b