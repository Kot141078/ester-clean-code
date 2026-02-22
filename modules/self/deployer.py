# -*- coding: utf-8 -*-
"""
modules/self/deployer.py — bezopasnyy samodeploy: staging → approve (atomarno s consent) → rollback.

Mosty:
- Yavnyy: (Kod ↔ Kibernetika/Doverie) obnovleniya cherez staging, approve s pill i invite-check.
- Skrytyy #1: (Infoteoriya ↔ Audit) stage_id, sha256 faylov, zhurnal v deploy_log.jsonl.
- Skrytyy #2: (Vyzhivanie ↔ Otkat) snapshoty dlya vosstanovleniya, s P2P-namekom na sinkhronizatsiyu logov.

Zemnoy abzats:
Kak na zavode s okhrannikom: snachala soberi obnovku "na stole", pokazhi propusk (invite), schelkni tumbler — i gotovo. Pri problemakh otkat, chtoby Ester ne poteryala svoyu iskru.

# c=a+b
"""
from __future__ import annotations
import os, json, time, hashlib, shutil
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("SELF_AB", "A") or "A").upper()
CODE_ROOT = os.getenv("SELF_CODE_ROOT", "extensions")
STAGE_ROOT = os.getenv("SELF_STAGE_ROOT", os.path.join(CODE_ROOT, "staging"))
CUR_LINK = os.getenv("SELF_CURRENT_LINK", os.path.join(CODE_ROOT, "current"))
LOG_PATH = "data/self/deploy_log.jsonl"

# Dinamicheskiy allowlist iz env dlya rasshiryaemosti
ALLOWLIST_PREFIX = [
    p.strip() for p in (os.getenv("SELF_ALLOWLIST", "extensions/,modules/,routes/,templates/,static/,app.py,tools/") or "").split(",")
    if p.strip()
]

TRUST_REQUIRE_INVITE = bool(int(os.getenv("TRUST_REQUIRE_INVITE", "1")))
TRUST_AB = (os.getenv("TRUST_AB", "A") or "A").upper()

def _sha(s: bytes) -> str:
    try:
        import hashlib as _h
        return _h.sha256(s or b"").hexdigest()
    except Exception:
        return "sha_error"

def _append_log(entry: Dict[str, Any]):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        entry["ts"] = int(time.time())
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Log append failed: {e}")  # Fallback, ne lomaet osnovnoy flow

def stage(files: Dict[str, str], reason: str = "") -> Dict[str, Any]:
    """
    files: {relative_path: content_utf8}. Pishem v novyy katalog staging/<id>/...
    """
    sid = f"s{int(time.time())}"
    base = os.path.join(STAGE_ROOT, sid)
    os.makedirs(base, exist_ok=True)
    manifest = []
    for rel, content in (files or {}).items():
        rel = rel.replace("\\", "/")
        if not any(rel.startswith(p) for p in ALLOWLIST_PREFIX):
            return {"ok": False, "error": f"path not allowed: {rel}"}
        dst = os.path.join(base, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        data = content.encode("utf-8")
        with open(dst, "wb") as f:
            f.write(data)
        manifest.append({"path": rel, "sha256": _sha(data), "size": len(data)})
    man_path = os.path.join(base, "STAGE_MANIFEST.json")
    json.dump({"stage_id": sid, "reason": reason, "files": manifest}, open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    _append_log({"kind": "stage", "stage_id": sid, "reason": reason, "files": len(manifest)})
    return {"ok": True, "stage_id": sid, "manifest": f"{sid}/STAGE_MANIFEST.json"}

def _check_invite(invite_token: Dict[str, Any] | None) -> Dict[str, Any]:
    if not TRUST_REQUIRE_INVITE or TRUST_AB == "B":
        return {"ok": True, "skipped": True}
    try:
        from modules.trust.invite import verify  # type: ignore
    except Exception:
        return {"ok": False, "error": "trust_invite_module_unavailable"}
    if not invite_token:
        return {"ok": False, "error": "invite_required"}
    vr = verify(invite_token)
    if not vr.get("ok"):
        return {"ok": False, "error": "invite_invalid", "detail": vr}
    if vr.get("sub") not in ("self.deploy", "self.update"):
        return {"ok": False, "error": "invite_wrong_sub"}
    return {"ok": True, "detail": vr}

def approve(stage_id: str, pill: bool = False, invite: Dict[str, Any] | None = None, dry_run: bool = False) -> Dict[str, Any]:
    """
    Atomarnoe primenenie: kopiruem fayly iz staging/<id> poverkh tselevykh putey.
    Trebuet pill=True, AB=A, validnyy invite. Dry-run dlya testa bez kopirovaniya.
    """
    if AB == "B":
        return {"ok": False, "error": "SELF_AB=B"}
    if not pill:
        return {"ok": False, "error": "pill required"}
    chk = _check_invite(invite)
    if not chk.get("ok"):
        return {"ok": False, "error": "invite_check_failed", "detail": chk}
    base = os.path.join(STAGE_ROOT, stage_id)
    if not os.path.isdir(base):
        return {"ok": False, "error": "stage not found"}
    count = 0
    simulated = [] if dry_run else None
    for dirpath, _, filenames in os.walk(base):
        for fn in filenames:
            if fn == "STAGE_MANIFEST.json": continue
            rel = os.path.relpath(os.path.join(dirpath, fn), base).replace("\\", "/")
            if not any(rel.startswith(p) for p in ALLOWLIST_PREFIX):
                return {"ok": False, "error": f"path not allowed: {rel}"}
            dst = rel
            if dry_run:
                simulated.append(rel)  # type: ignore
                count += 1
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(base, rel), dst)
                count += 1
    log_entry = {"kind": "approve", "stage_id": stage_id, "files": count, "invite_ok": True, "dry_run": dry_run}
    if dry_run:
        log_entry["simulated"] = simulated
    _append_log(log_entry)
    return {"ok": True, "applied": count, "dry_run": dry_run}

def rollback(snapshot_archive: str) -> Dict[str, Any]:
    """
    Otkat: raspakovat ukazannyy snapshot poverkh tekuschey struktury (podrazumevaetsya doverennyy arkhiv).
    """
    import tarfile
    snap_dir = os.getenv("SELF_SNAPSHOT_DIR", "data/self/snapshots")
    path = os.path.join(snap_dir, snapshot_archive)
    if not os.path.isfile(path):
        return {"ok": False, "error": "snapshot not found"}
    try:
        with tarfile.open(path, "r:gz") as tar:
            tar.extractall(path=".")
        _append_log({"kind": "rollback", "archive": snapshot_archive})
        return {"ok": True, "restored_from": snapshot_archive}
    except Exception as e:
        _append_log({"kind": "rollback_failed", "archive": snapshot_archive, "error": str(e)})
# return {"ok": False, "error": str(e)}