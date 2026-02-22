# -*- coding: utf-8 -*-
"""
modules/self/archiver.py — samosnimki koda/struktury: .tar.gz + manifest s sha256 i webseed-monetkoy.

Mosty:
- Yavnyy: (Inzheneriya ↔ Set) gotovim perenosimyy arkhiv + manifest i optsionalnyy .torrent, chtoby sestry mogli podtyanut.
- Skrytyy #1: (Infoteoriya ↔ Audit) katalog snapshotov, kheshi i provenans ostayutsya dlya proverki tselostnosti.
- Skrytyy #2: (Kibernetika ↔ Vyzhivanie) snapshoty pitayut otkaty/samosoborku i rasprostranyayutsya legalnym sposobom (HTTP/BT).

Zemnoy abzats:
Eto «obraz sistemy»: zaarkhivirovali, poschitali khesh, polozhili manifest, dali ssylku — mozhno razvorachivat na drugikh uzlakh.

# c=a+b
"""
from __future__ import annotations
import os, io, tarfile, time, hashlib, json, shutil, subprocess
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SNAP_DIR = os.getenv("SELF_SNAPSHOT_DIR","data/self/snapshots")
INCLUDE_CSV = os.getenv("SELF_SNAPSHOT_INCLUDE","extensions,modules,routes,templates,static,app.py,requirements.txt,tools")

def _ensure():
    os.makedirs(SNAP_DIR, exist_ok=True)

def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def _manifest_entry(path: str) -> Dict[str, Any]:
    st = os.stat(path)
    return {"path": path, "size": st.st_size, "sha256": _file_sha256(path)}

def _iter_include() -> List[str]:
    inc = [p.strip() for p in INCLUDE_CSV.split(",") if p.strip()]
    return [p for p in inc if os.path.exists(p)]

def create_snapshot(note: str = "") -> Dict[str, Any]:
    _ensure()
    ts = int(time.time())
    includes = _iter_include()
    # sozdaem vremennyy tar.gz
    tar_name = f"ester_snapshot_{ts}.tar.gz"
    tar_path = os.path.join(SNAP_DIR, tar_name)
    manifest: Dict[str, Any] = {"created_ts": ts, "includes": includes, "note": note, "files": []}
    with tarfile.open(tar_path, "w:gz") as tar:
        for root in includes:
            if os.path.isdir(root):
                for dirpath, _, filenames in os.walk(root):
                    for fn in filenames:
                        p = os.path.join(dirpath, fn)
                        if "/.git" in p or "/__pycache__" in p or p.startswith("data/"):
                            continue
                        tar.add(p)
                        try:
                            manifest["files"].append(_manifest_entry(p))
                        except Exception:
                            pass
            elif os.path.isfile(root):
                tar.add(root)
                try:
                    manifest["files"].append(_manifest_entry(root))
                except Exception:
                    pass
    # khesh arkhiva
    arc_sha = _file_sha256(tar_path)
    man_path = os.path.join(SNAP_DIR, f"{tar_name}.manifest.json")
    manifest["archive"] = {"path": tar_name, "sha256": arc_sha, "size": os.path.getsize(tar_path)}
    json.dump(manifest, open(man_path,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "archive": tar_name, "sha256": arc_sha, "manifest": os.path.basename(man_path)}

def list_snapshots() -> Dict[str, Any]:
    _ensure()
    items = []
    for fn in sorted(os.listdir(SNAP_DIR)):
        if fn.endswith(".tar.gz"):
            mp = os.path.join(SNAP_DIR, f"{fn}.manifest.json")
            man = {}
            try:
                man = json.load(open(mp,"r",encoding="utf-8"))
            except Exception:
                pass
            items.append({"archive": fn, "manifest": os.path.basename(mp), "meta": man.get("note",""), "sha256": (man.get("archive") or {}).get("sha256")})
    return {"ok": True, "items": items}

def build_torrent(archive_name: str, webseed_url: str | None = None) -> Dict[str, Any]:
    """
    Pytaemsya sozdat .torrent legalno: nuzhen mktorrent ili transmission-create.
    Bez SHELL — tolko opisanie «kak sdelat».
    """
    allow_shell = bool(int(os.getenv("SELF_ALLOW_SHELL","0")))
    arc_path = os.path.join(SNAP_DIR, archive_name)
    if not os.path.isfile(arc_path):
        return {"ok": False, "error":"archive not found"}
    torrent = archive_name.replace(".tar.gz",".torrent")
    tor_path = os.path.join(SNAP_DIR, torrent)
    cmd = None
    if allow_shell and shutil.which("mktorrent"):
        cmd = ["mktorrent","-o", tor_path, "-a", "udp://tracker.opentrackr.org:1337/announce"]
        if webseed_url: cmd += ["-w", webseed_url]
        cmd += [arc_path]
    elif allow_shell and shutil.which("transmission-create"):
        cmd = ["transmission-create","-o", tor_path, arc_path]
        # webseed podderzhka zavisit ot versii
    if cmd:
        try:
            subprocess.check_call(cmd, timeout=21600)
            return {"ok": True, "torrent": os.path.basename(tor_path)}
        except Exception as e:
            return {"ok": False, "error": f"torrent tool failed: {e}"}
    # Bez shell — tolko instruktsiya
    return {"ok": True, "hint": "run locally", "suggest": f"mktorrent -o {tor_path} -a udp://tracker.opentrackr.org:1337/announce -w {webseed_url or '<webseed>'} {arc_path}"}
# c=a+b



