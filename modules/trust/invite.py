# -*- coding: utf-8 -*-
"""
modules/trust/invite.py — «kapsula soglasiya» (priglashenie): vypusk i proverka podpisey c TTL.

Mosty:
- Yavnyy: (Doverie ↔ Deystviya) tolko s validnym priglasheniem razreshaem opasnye shagi (naprimer, samodeploy).
- Skrytyy #1: (Infoteoriya ↔ Audit) payload imeet sha256, nonce, iat/exp; proveryaem s uchetom razbega chasov.
- Skrytyy #2: (Kibernetika ↔ Vyzhivanie) shablon obschey i bezopasnoy «voli» mezhdu sestrami.

Zemnoy abzats:
Eto «podpisannaya zapiska»: kto, komu, chto razreshaet i do kakogo vremeni. Bez nee — tumbler ne schelkaem.

# c=a+b
"""
from __future__ import annotations
import base64, json, os, time, hashlib
from typing import Any, Dict
from modules.trust.keystore import get_local_identity, sign_bytes, verify_bytes
from modules.trust.peers import find_by_id
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SKEW = int(os.getenv("TRUST_CLOCK_SKEW_SEC","120"))

def issue(sub: str, scope: str, ttl_sec: int, archive_sha: str | None, aud: str) -> Dict[str, Any]:
    iss = "local"
    iat = int(time.time())
    exp = iat + max(30, int(ttl_sec))
    payload = {
        "iss": iss, "aud": aud, "sub": sub, "scope": scope,
        "iat": iat, "exp": exp, "archive_sha": archive_sha or "", "nonce": base64.b64encode(os.urandom(12)).decode("ascii")
    }
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    sig = sign_bytes(data)
    ident = get_local_identity()
    token = {"alg": sig["alg"], "sig": sig["sig"], "payload": payload, "issuer_pub": ident["pubkey"]}
    token["payload_sha256"] = hashlib.sha256(data).hexdigest()
    return {"ok": True, "token": token}

def verify(token: Dict[str, Any]) -> Dict[str, Any]:
    try:
        alg = str(token.get("alg",""))
        sig = str(token.get("sig",""))
        payload = token.get("payload") or {}
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        now = int(time.time())
        iat, exp = int(payload.get("iat",0)), int(payload.get("exp",0))
        if not (iat - SKEW <= now <= exp + SKEW):
            return {"ok": False, "error":"expired_or_in_future","iat":iat,"exp":exp,"now":now}
        iss = str(payload.get("iss",""))
        aud = str(payload.get("aud",""))
        # lokalnye priglasheniya (iss="local"): proveryaem lokalnym klyuchom (HMAC-follbek dopustim)
        pub = str(token.get("issuer_pub",""))
        if iss != "local":
            # vneshnie priglasheniya — ischem pira
            peer = find_by_id(iss)
            if not peer:
                return {"ok": False, "error":"unknown_issuer"}
            if peer.get("alg") != alg:
                return {"ok": False, "error":"alg_mismatch"}
            pub = str(peer.get("pubkey",""))
        ok = verify_bytes(data, alg, sig, pub)
        return {"ok": bool(ok), "alg": alg, "aud": aud, "sub": str(payload.get("sub","")), "payload": payload}
    except Exception as e:
        return {"ok": False, "error": f"bad_token:{e}"}
# c=a+b