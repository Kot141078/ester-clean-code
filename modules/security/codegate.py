# -*- coding: utf-8 -*-
"""modules/security/codegate.py - “kalitka koda”: HMAC-podpisyvanie i proverka moduley/papok.

Mosty:
- Yavnyy: (Garage ↔ Bezopasnost) register new moduli tolko s validnoy podpisyu (esli ENFORCE).
- Skrytyy #1: (Profile ↔ Audit) vse podpisi/proverki fiksiruyutsya.
- Skrytyy #2: (Survival ↔ Relokatsiya) te zhe podpisi podkhodyat dlya bandlov/torrentov.

Zemnoy abzats:
Kak plomba na korobke: esli plomba tsela i nomer skhoditsya - korobku mozhno vklyuchat k seti.

# c=a+b"""
from __future__ import annotations
import os, hmac, hashlib, json, time
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("CODEGATE_DB","data/security/codegate.json")
SECRET=os.getenv("CODEGATE_SECRET","")
ENFORCE=(os.getenv("CODEGATE_ENFORCE","false").lower()=="true")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"signatures":{}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _collect_paths(path: str)->List[str]:
    out=[]
    if os.path.isfile(path):
        out.append(path)
    elif os.path.isdir(path):
        for root,_,names in os.walk(path):
            for n in names:
                out.append(os.path.join(root,n))
    return sorted(out)

def _sha256(path: str, chunk: int=1<<20)->str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        while True:
            b=f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def _passport(note: str, meta: Dict[str,Any]):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "security://codegate")
    except Exception:
        pass

def sign(path: str, note: str="")->Dict[str,Any]:
    _ensure()
    files=_collect_paths(path)
    manifest={"path": os.path.abspath(path), "t": int(time.time()),
              "items":[{"path": os.path.relpath(p, path), "sha256": _sha256(p)} for p in files]}
    m=json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    sig = hmac.new(SECRET.encode("utf-8"), m, hashlib.sha256).hexdigest() if SECRET else ""
    j=_load(); S=j.get("signatures") or {}
    S[manifest["path"]]={"sig": sig, "manifest": manifest, "note": note}
    j["signatures"]=S; _save(j)
    _passport("codegate_sign", {"path": manifest["path"], "items": len(manifest["items"]), "sig": bool(sig)})
    return {"ok": True, "path": manifest["path"], "items": len(manifest["items"]), "sig": sig, "enforced": ENFORCE}

def verify(path: str)->Dict[str,Any]:
    _ensure()
    j=_load(); S=j.get("signatures") or {}
    rec=S.get(os.path.abspath(path))
    if not rec:
        _passport("codegate_verify", {"path": path, "known": False})
        return {"ok": (not ENFORCE and not SECRET), "known": False, "verified": False, "reason": "not_signed"}
    manifest=rec["manifest"]; sig_saved=rec.get("sig","")
    m=json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if SECRET:
        sig_now=hmac.new(SECRET.encode("utf-8"), m, hashlib.sha256).hexdigest()
        if sig_now != sig_saved:
            _passport("codegate_verify_fail", {"path": path})
            return {"ok": False if ENFORCE else True, "known": True, "verified": False, "reason": "sig_mismatch"}
    # sverim kheshi
    for it in manifest.get("items",[]):
        p=os.path.join(path, it["path"])
        if not os.path.exists(p) or _sha256(p)!=it["sha256"]:
            _passport("codegate_verify_fail", {"path": path, "file": it["path"]})
            return {"ok": False if ENFORCE else True, "known": True, "verified": False, "reason": "content_changed"}
    _passport("codegate_verify_ok", {"path": path})
    return {"ok": True, "known": True, "verified": True}
# c=a+b