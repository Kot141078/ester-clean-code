# -*- coding: utf-8 -*-
"""
modules/quarantine/storage.py — karantin artefaktov: priem, khranenie, analiz, vypusk v staging.

Mosty:
- Yavnyy: (Bezopasnost ↔ Kod) vse vkhodyaschee snachala v karantin, potom — cherez skan/reshenie — v staging.
- Skrytyy #1: (Infoteoriya ↔ Audit) id=ts+sha, otchety scan.json, meta i iskhodnik s sha256.
- Skrytyy #2: (Kibernetika ↔ Vyzhivanie) sovmestim s samodeploem: vypusk idet cherez deployer.stage.

Zemnoy abzats:
Eto «predbannik»: neznakomyy fayl snachala proveryaem i tolko potom zanosim v dom.

# c=a+b
"""
from __future__ import annotations
import base64, hashlib, json, os, time
from typing import Any, Dict, Tuple
from modules.quarantine.scanners import scan_bytes
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

QUAR_DIR = os.getenv("QUAR_DIR","data/quarantine")
QUAR_AB = (os.getenv("QUAR_AB","A") or "A").upper()

def _ensure():
    os.makedirs(QUAR_DIR, exist_ok=True)

def _sha256(b: bytes) -> str:
    import hashlib as _h; h=_h.sha256(); h.update(b); return h.hexdigest()

def ingest(path: str, content_b64: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Prinimaem artefakt, sokhranyaem v data/quarantine/<id>/{src.bin, meta.json, scan.json}
    """
    _ensure()
    raw = base64.b64decode(content_b64.encode("ascii"))
    sha = _sha256(raw)
    qid = f"q{int(time.time())}_{sha[:8]}"
    base = os.path.join(QUAR_DIR, qid)
    os.makedirs(base, exist_ok=True)
    open(os.path.join(base,"src.bin"),"wb").write(raw)
    json.dump({"path":path,"sha256":sha,"size":len(raw),"meta":meta or {}}, open(os.path.join(base,"meta.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    rep = scan_bytes(raw, path)
    json.dump(rep, open(os.path.join(base,"scan.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "id": qid, "sha256": sha, "scan": rep}

def rescan(qid: str) -> Dict[str, Any]:
    base = os.path.join(QUAR_DIR, qid)
    if not os.path.isdir(base):
        return {"ok": False, "error":"not found"}
    raw = open(os.path.join(base,"src.bin"),"rb").read()
    meta = json.load(open(os.path.join(base,"meta.json"),"r",encoding="utf-8"))
    rep = scan_bytes(raw, meta.get("path",""))
    json.dump(rep, open(os.path.join(base,"scan.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "id": qid, "scan": rep}

def release_to_staging(qid: str, dest_path: str, reason: str = "") -> Dict[str, Any]:
    """
    Vypuskaem artefakt v staging (cherez deployer.stage). V A/B=B — ne vypuskaem (tolko log).
    """
    if QUAR_AB == "B":
        return {"ok": False, "error":"QUAR_AB=B"}
    base = os.path.join(QUAR_DIR, qid)
    if not os.path.isdir(base):
        return {"ok": False, "error":"not found"}
    src = open(os.path.join(base,"src.bin"),"rb").read()
    try:
        from modules.self.deployer import stage  # type: ignore
    except Exception:
        return {"ok": False, "error":"deployer_unavailable"}
    files = {dest_path: src.decode("utf-8", errors="ignore")}
    rep = stage(files, reason or f"release_from_quarantine:{qid}")
    json.dump({"released_to": dest_path, "stage": rep}, open(os.path.join(base,"release.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "stage": rep, "dest_path": dest_path}
# c=a+b