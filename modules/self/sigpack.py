# -*- coding: utf-8 -*-
"""
modules/self/sigpack.py — podpis/proverka snapshotov (arkhivov) s ispolzovaniem keystore (ed25519 ili HMAC-follbek).

Mosty:
- Yavnyy: (Inzheneriya ↔ Doverie) podpisyvaem arkhiv i manifest dlya proverki tselostnosti.
- Skrytyy #1: (Infoteoriya ↔ Audit) sokhranyaem .sig.json ryadom s arkhivom.
- Skrytyy #2: (Vyzhivanie ↔ Samodeploy) proverka podpisi pered otkatom/appruvom.

Zemnoy abzats:
Arkhiv bez podpisi — prosto fayl. S podpisyu — proveryaemaya «posylka», kotoruyu mozhno smelo primenyat.

# c=a+b
"""
from __future__ import annotations
import json, os, hashlib
from typing import Any, Dict
from modules.trust.keystore import get_local_identity, sign_bytes, verify_bytes
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SNAP_DIR = os.getenv("SELF_SNAPSHOT_DIR","data/self/snapshots")

def _load_manifest(archive: str) -> Dict[str, Any]:
    mp = os.path.join(SNAP_DIR, f"{archive}.manifest.json")
    return json.load(open(mp,"r",encoding="utf-8"))

def _archive_path(archive: str) -> str:
    return os.path.join(SNAP_DIR, archive)

def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def sign_archive(archive: str) -> Dict[str, Any]:
    arc = _archive_path(archive)
    if not os.path.isfile(arc):
        return {"ok": False, "error":"archive not found"}
    man = _load_manifest(archive)
    arc_sha = _file_sha256(arc)
    data = {"archive": archive, "sha256": arc_sha, "manifest_sha256": hashlib.sha256(json.dumps(man,ensure_ascii=False,sort_keys=True).encode("utf-8")).hexdigest()}
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    sig = sign_bytes(raw)
    ident = get_local_identity()
    obj = {"alg": sig["alg"], "sig": sig["sig"], "data": data, "issuer_pub": ident["pubkey"]}
    outp = os.path.join(SNAP_DIR, f"{archive}.sig.json")
    json.dump(obj, open(outp,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "sigfile": os.path.basename(outp), "alg": sig["alg"], "sha256": data["sha256"]}

def verify_archive(archive: str) -> Dict[str, Any]:
    arc = _archive_path(archive)
    sigp = os.path.join(SNAP_DIR, f"{archive}.sig.json")
    if not (os.path.isfile(arc) and os.path.isfile(sigp)):
        return {"ok": False, "error":"missing_archive_or_sig"}
    sig = json.load(open(sigp,"r",encoding="utf-8"))
    data = json.dumps(sig.get("data"), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ok = verify_bytes(data, sig.get("alg",""), sig.get("sig",""), sig.get("issuer_pub",""))
    return {"ok": bool(ok), "alg": sig.get("alg",""), "sha256": (sig.get("data") or {}).get("sha256")}
# c=a+b