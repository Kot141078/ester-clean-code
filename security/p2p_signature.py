# -*- coding: utf-8 -*-
"""
security/p2p_signature.py — edinyy standart podpisi P2P s obratnoy sovmestimostyu.

Mosty:
- Yavnyy (Dok ↔ Realizatsiya): edinye zagolovki/formuly sovpadayut so skriptom podpisi i smoke-shagami.
- Skrytyy #1 (CLI ↔ Server): scripts/p2p_sign.py pechataet korrektnye X-P2P-*; server verifitsiruet ikh.
- Skrytyy #2 (Legacy ↔ New): prinimaem X-P2P-Auth i X-HMAC-Signature kak aliasy (deprecation).

Zemnoy abzats:
Odin format «po umolchaniyu» (X-P2P-Signature + X-P2P-Ts) ↓ 401/vremya diagnostiki, no starye klienty ne lomayutsya.
# c=a+b
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Edinye imena zagolovkov «novogo» standarta
HDR_TS = "X-P2P-Ts"
HDR_NODE = "X-P2P-Node"
HDR_SIG = "X-P2P-Signature"

# Dopustimye «aliyasnye» zagolovki iz legasi-klientov (vremenno; deprecation)
HDR_ALIASES = ("X-P2P-Auth", "X-HMAC-Signature")

# Formula «novogo» standarta: HMAC(secret, f"{ts}\n{method}\n{path}\n{sha256(body)}")
def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b or b"").hexdigest()

def sign_hmac(secret: str, ts: int, method: str, path: str, body: bytes) -> str:
    msg = f"{ts}\n{method.upper()}\n{path}\n{_sha256_hex(body)}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

# Uproschennyy legasi-variant (istoricheskiy): HMAC(secret, f"{method}\n{path}\n{ts}")
def sign_hmac_legacy(secret: str, ts: int, method: str, path: str) -> str:
    msg = f"{method.upper()}\n{path}\n{ts}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

def _get_secret() -> str:
    """
    Istochnik sekreta dlya P2P. Podderzhivaem ESTER_P2P_SECRET (osnovnoy).
    """
    return os.getenv("ESTER_P2P_SECRET", "")

def _parse_ts(raw: str) -> Optional[int]:
    try:
        v = int(raw)
        return v if v > 0 else None
    except Exception:
        return None

def _clock_ok(ts: int, now: Optional[int] = None, skew: Optional[int] = None) -> bool:
    now = now or int(time.time())
    if skew is None:
        try:
            skew = int(os.getenv("ESTER_P2P_TS_WINDOW", "300") or "300")
        except Exception:
            skew = 300
    return abs(now - ts) <= max(1, int(skew))

def _extract_new(headers) -> Tuple[Optional[int], Optional[str]]:
    ts = _parse_ts(headers.get(HDR_TS, ""))
    sig = headers.get(HDR_SIG, "")
    return ts, sig if sig else None

def _extract_legacy(headers) -> Tuple[Optional[int], Optional[str], str]:
    """
    Vozvraschaet (ts, sig, kind) dlya legasi-aliyasov:
      kind = "x-p2p-auth" | "x-hmac-signature"
    """
    # Variant 1: X-P2P-Auth (starye klienty) — signatura po uproschennoy formule
    if headers.get("X-P2P-Auth"):
        ts = _parse_ts(headers.get(HDR_TS, ""))
        return ts, headers.get("X-P2P-Auth"), "x-p2p-auth"
    # Variant 2: X-HMAC-Signature (sosedniy P2P-klient) — HMAC po telu kak zagolovok
    if headers.get("X-HMAC-Signature"):
        # V etom formate timestamp mozhet otsutstvovat — tut proverim pozzhe (bez ts)
        return None, headers.get("X-HMAC-Signature"), "x-hmac-signature"
    return None, None, ""

def verify(method: str, path: str, headers, body: bytes) -> Optional[str]:
    """
    Zhestkaya proverka «novogo» formata: X-P2P-Signature + X-P2P-Ts.
    Vozvraschaet None esli vse ok, inache stroku-oshibku.
    """
    secret = _get_secret()
    if not secret:
        # Esli sekret ne zadan — podpis poka ne trebuetsya
        return None
    ts, sig = _extract_new(headers)
    if not ts or not sig:
        return "p2p_signature_required"
    if not _clock_ok(ts):
        return "p2p_clock_skew"
    want = sign_hmac(secret, ts, method, path, body)
    if not hmac.compare_digest(sig, want):
        return "p2p_bad_signature"
    return None

def verify_any(headers, method: str, path: str, body: bytes) -> Optional[str]:
    """
    Universalnaya proverka:
      1) Snachala pytaemsya novyy format (X-P2P-Signature + X-P2P-Ts).
      2) Zatem X-P2P-Auth (legacy) — uproschennaya formula.
      3) Zatem X-HMAC-Signature (replikatsionnyy sosed) — prinimaem kak «spets-sluchay».
    """
    # 1) Novyy format
    err = verify(method=method, path=path, headers=headers, body=body)
    if err is None:
        return None

    secret = _get_secret()
    if not secret:
        return None  # net sekreta → podpis ne obyazatelna

    # 2) Legasi X-P2P-Auth
    ts, sig, kind = _extract_legacy(headers)
    if kind == "x-p2p-auth":
        if not ts or not sig:
            return "p2p_signature_required"
        if not _clock_ok(ts):
            return "p2p_clock_skew"
        want = sign_hmac_legacy(secret, ts, method, path)
        if not hmac.compare_digest(sig, want):
            return "p2p_bad_signature"
        return None

    # 3) «Sosedniy» format X-HMAC-Signature (sovmestimost s klientom /p2p/push)
    # Etot format podpisyvaet TELO (kak v security/signing.header_signature),
    # poetomu ispolzuem ego kak «poslablenie» tolko dlya bezopasnykh putey p2p/*
    sig_hdr = headers.get("X-HMAC-Signature", "")
    if sig_hdr:
        if not str(path).startswith("/p2p/"):
            return "p2p_bad_signature"
        try:
            from security.signing import verify_signature  # type: ignore
        except Exception:
            return "p2p_bad_signature"
        ok = verify_signature(body or b"", sig_hdr)
        return None if ok else "p2p_bad_signature"

    # Esli nichego ne podoshlo — vozvraschaem iskhodnuyu oshibku
    return err
