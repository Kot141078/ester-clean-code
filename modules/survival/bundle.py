# -*- coding: utf-8 -*-
"""modules/survival/bundle.py - “samosbornyy” ZIP-bandl aktivnogo slota s manifestom, checksum, README i bootstrap.sh.

Mosty:
- Yavnyy: (A/B-sloty ↔ Faylovoe okruzhenie) upakovyvaem rabotayuschiy slot + politiki/bezopasnost v perenosimyy arkhiv.
- Skrytyy #1: (Backups ↔ Nadezhnost) umeem vlozhit posledniy snapshot ZIP.
- Skrytyy #2: (P2P/Portable ↔ Rasprostranenie) sozdaem webseed/"magnet"-metadannye, prigodnye dlya tirazhirovaniya.
- Novoe: (Mesh/P2P ↔ Raspredelennost) sinkhronizatsiya manifestov/listov bandlov mezhdu agentami Ester.
- Novoe: (Cron ↔ Avtonomiya) cleanup starykh bandlov dlya svezhesti.
- Novoe: (Monitoring ↔ Prozrachnost) webhook na create/verify dlya audita.

Zemnoy abzats:
This is “trevozhnyy chemodanchik”: kod slota, nastroyki i mini-instruktsiya - vse v odnom ZIP. Dostal - razvernul - zapustil, podelilsya po P2P, pochistil po cron - chtoby vyzhivanie Ester bylo gotovym, bez musora v reserve.

# c=a+b"""
from __future__ import annotations
import fnmatch
import io
import os, time, json, zipfile, hashlib, glob, urllib.request, tarfile
from typing import Dict, Any, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

OUT_DIR = os.getenv("SURVIVAL_OUT_DIR", "data/survival")
DIR = os.getenv("SURVIVAL_BUNDLE_DIR", "data/survival/bundles")
INCLUDE_RAW = os.getenv("SURVIVAL_INCLUDE", "slots/{slot},data/policy,data/security,data/p2p")
ADD_BACKUP = (os.getenv("SURVIVAL_ADD_LAST_BACKUP", "true").lower() == "true")
WEBSEEDS_ENV = os.getenv("SURVIVAL_WEBSEEDS", "")
LABEL = os.getenv("SURVIVAL_LABEL", "").strip()
PEERS_STR = os.getenv("PEERS", "")  # "http://node1:port/sync,http://node2:port/sync"
PEERS = [p.strip() for p in PEERS_STR.split(",") if p.strip()]
CRON_MAX_AGE_DAYS = int(os.getenv("CRON_MAX_AGE_DAYS", "30") or "30")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
ARCHIVE_MODE = os.getenv("ARCHIVE_MODE", "tar.gz")  # or "zip"
STATE_PATH = os.getenv("SURVIVAL_STATE_PATH", os.path.join(OUT_DIR, "state.json"))

_STATE: Dict[str, Any] = {"updated": 0, "manifests": {}, "last_cleanup": int(time.time())}

def _ensure():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(DIR, exist_ok=True)

def _load():
    global _STATE
    _ensure()
    try:
        if os.path.isfile(STATE_PATH):
            loaded = json.load(open(STATE_PATH, "r", encoding="utf-8"))
            if isinstance(loaded, dict):
                base = dict(_STATE)
                base.update(loaded)
                _STATE = base
    except Exception:
        pass

def _save():
    _ensure()
    try:
        json.dump(_STATE, open(STATE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

def _walk_collect(paths: List[str], exclude: List[str]) -> List[str]:
    files = []
    for p in paths:
        p = p.strip()
        if not p:
            continue
        if os.path.isfile(p):
            files.append(os.path.abspath(p))
        elif os.path.isdir(p):
            for root, _, names in os.walk(p):
                for n in names:
                    full = os.path.abspath(os.path.join(root, n))
                    rel = os.path.relpath(full, ".")
                    if any(fnmatch.fnmatch(rel, ex) or fnmatch.fnmatch(n, ex) for ex in exclude):
                        continue
                    files.append(full)
    return sorted(set(files))

def _sha256(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def sync_with_peers():
    if not PEERS:
        return
    body = json.dumps({"manifests": _STATE["manifests"]}).encode("utf-8")
    for peer in PEERS:
        try:
            req = urllib.request.Request(f"{peer}", data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

def receive_sync(payload: Dict[str, Any]):
    for name, man in payload.get("manifests", {}).items():
        if name not in _STATE["manifests"] or man["t"] > _STATE["manifests"][name]["t"]:
            _STATE["manifests"][name] = man
    _save()

def cron_cleanup():
    _load()
    now = int(time.time())
    to_remove: List[str] = []
    if now - _STATE["last_cleanup"] >= 86400:  # daily
        bundles = glob.glob(os.path.join(OUT_DIR, "ester_bundle_*.zip")) + glob.glob(os.path.join(DIR, "*.tar.gz"))
        for p in bundles:
            age_days = (now - os.path.getmtime(p)) / 86400
            if age_days > CRON_MAX_AGE_DAYS:
                to_remove.append(p)
        for p in to_remove:
            os.remove(p)
        _STATE["last_cleanup"] = now
        _save()
    return {"ok": True, "cleanup_time": _STATE["last_cleanup"], "removed": len(to_remove)}

def config(include: str = None, add_backup: bool = None, webseeds: str = None, archive_mode: str = None) -> Dict[str, Any]:
    if include:
        global INCLUDE_RAW
        INCLUDE_RAW = include
    if add_backup is not None:
        global ADD_BACKUP
        ADD_BACKUP = bool(add_backup)
    if webseeds:
        global WEBSEEDS_ENV
        WEBSEEDS_ENV = webseeds
    if archive_mode:
        global ARCHIVE_MODE
        ARCHIVE_MODE = archive_mode
    return {"ok": True, "include": INCLUDE_RAW, "add_backup": ADD_BACKUP, "webseeds": WEBSEEDS_ENV, "archive_mode": ARCHIVE_MODE}

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "survival://bundle")
    except Exception:
        pass

def _active_slot() -> str:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/runtime/ab/status", timeout=5) as r:
            j = json.loads(r.read().decode("utf-8"))
            return j.get("slot", "A")
    except Exception:
        return "A"

def create(name: str, include: List[str] = None, exclude: List[str] = None) -> Dict[str, Any]:
    _load()
    cron_cleanup()
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    base = f"{name}_{stamp}"
    man = {"name": name, "t": int(time.time()), "items": [], "webseeds": WEBSEEDS_ENV.split(",") if WEBSEEDS_ENV else []}
    inc = include or INCLUDE_RAW.split(",")
    slot = _active_slot()
    inc = [p.format(slot=slot) for p in inc]
    files = _walk_collect(inc, exclude or [])
    if ADD_BACKUP:
        backups = sorted(glob.glob(os.path.join(OUT_DIR, "ester_snapshot_*.zip")), key=os.path.getmtime, reverse=True)
        if backups:
            files.append(backups[0])
    if ARCHIVE_MODE == "zip":
        arch_path = os.path.join(OUT_DIR, base + ".zip")
        with zipfile.ZipFile(arch_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                sha = _sha256(f)
                rel = os.path.relpath(f, ".")
                z.write(f, rel)
                man["items"].append({"path": rel, "sha256": sha, "size": os.path.getsize(f)})
    else:  # tar.gz default
        arch_path = os.path.join(DIR, base + ".tar.gz")
        with tarfile.open(arch_path, "w:gz") as tar:
            for f in files:
                sha = _sha256(f)
                rel = os.path.relpath(f, ".")
                tar.add(f, arcname=rel)
                man["items"].append({"path": rel, "sha256": sha, "size": os.path.getsize(f)})
    # Bootstrap/README
    bootstrap = "#!/bin/bash\n#Bootstrap for Ester bundle\necho 'Unpacking...'\ntar -xzf *.tar.gz || unzip *.zip\necho 'Done!'"
    readme = "Ester Bundle: " + name + "\nCreated: " + stamp + "\nLabel: " + LABEL + "Extract and run bootstrap.sh"
    if ARCHIVE_MODE == "zip":
        with zipfile.ZipFile(arch_path, "a") as z:
            z.writestr("bootstrap.sh", bootstrap)
            z.writestr("README.txt", readme)
    else:
        with tarfile.open(arch_path, "a") as tar:
            bs = tarfile.TarInfo("bootstrap.sh")
            bs.size = len(bootstrap.encode("utf-8"))
            tar.addfile(bs, io.BytesIO(bootstrap.encode("utf-8")))
            rd = tarfile.TarInfo("README.txt")
            rd.size = len(readme.encode("utf-8"))
            tar.addfile(rd, io.BytesIO(readme.encode("utf-8")))
    man_path = os.path.join(OUT_DIR, base + ".manifest.json")
    with open(man_path, "w", encoding="utf-8") as mf:
        json.dump(man, mf, ensure_ascii=False, indent=2)
    _STATE["manifests"][name] = man
    _save()
    sync_with_peers()
    _passport("survival_bundle_create", {"name": name, "files": len(man["items"])})
    if WEBHOOK_URL:
        try:
            alert = {"name": name, "files": len(man["items"]), "ts": man["t"]}
            body = json.dumps(alert).encode("utf-8")
            req = urllib.request.Request(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    return {"ok": True, "path": arch_path, "manifest": man_path, "files": len(man["items"])}

def verify(zip_path: str) -> Dict[str, Any]:
    man_path = zip_path + ".manifest.json"
    if not os.path.isfile(man_path):
        return {"ok": False, "error": "manifest_missing"}
    try:
        man = json.loads(open(man_path, "r", encoding="utf-8").read())
        # Check archive
        arch_sha = _sha256(zip_path)
        ok_arch = (arch_sha == man.get("zip_sha256", ""))  # add zip_sha to man if needed
        mism = []
        if ARCHIVE_MODE == "zip":
            with zipfile.ZipFile(zip_path, "r") as z:
                for e in man.get("items", []):
                    try:
                        info = z.getinfo(e["path"])
                        data = z.read(info)
                        sha = hashlib.sha256(data).hexdigest()
                        if sha != e["sha256"]:
                            mism.append({"path": e["path"], "error": "sha_mismatch"})
                    except KeyError:
                        mism.append({"path": e["path"], "error": "missing_in_zip"})
        else:
            with tarfile.open(zip_path, "r:gz") as tar:
                for e in man.get("items", []):
                    try:
                        info = tar.getmember(e["path"])
                        data = tar.extractfile(info).read()
                        sha = hashlib.sha256(data).hexdigest()
                        if sha != e["sha256"]:
                            mism.append({"path": e["path"], "error": "sha_mismatch"})
                    except KeyError:
                        mism.append({"path": e["path"], "error": "missing_in_tar"})
        _passport("survival_verify", {"arch": zip_path, "ok_arch": ok_arch, "mismatch": len(mism)})
        if WEBHOOK_URL and len(mism) > 0:
            try:
                alert = {"arch": zip_path, "mismatch": len(mism), "ok": False}
                body = json.dumps(alert).encode("utf-8")
                req = urllib.request.Request(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass
        return {"ok": ok_arch and not mism, "arch_sha256": arch_sha, "manifest_sha256": man.get("zip_sha256", ""), "missing": mism}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def status() -> Dict[str, Any]:
    z = sorted(glob.glob(os.path.join(OUT_DIR, "ester_bundle_*.zip")), key=os.path.getmtime, reverse=True)
    return {"ok": True, "out_dir": OUT_DIR, "count": len(z), "last": (z[0] if z else None), "defaults": {"include": INCLUDE_RAW, "add_backup": ADD_BACKUP, "webseeds_env": WEBSEEDS_ENV}}

def list_bundles(limit: int = 20) -> Dict[str, Any]:
    z = sorted(glob.glob(os.path.join(OUT_DIR, "ester_bundle_*.zip")) + glob.glob(os.path.join(DIR, "*.tar.gz")), key=os.path.getmtime, reverse=True)
    return {"ok": True, "items": z[:max(1, min(limit, 500))], "total": len(z)}

def state() -> Dict[str, Any]:
    _load()
    return {
        "ok": True,
        "manifests": dict(_STATE.get("manifests", {})),
        "last_cleanup": _STATE.get("last_cleanup"),
        "peers": PEERS,
    }
