# -*- coding: utf-8 -*-
"""modules/storage/targets.py - reestr tseley khraneniya (lokalno/oblako/pochta) + obnaruzhenie disks.

Format zapisi tseli (target):
{
  "id": "t_1712345678",
  "type": "local|s3|webdav|email",
  "name": "Chelovecheskoe imya",
  "enabled": true,
  "config": { ... },
  "created": 1712345678.0
}

Where config:
- local: { "path": "/srv/ester-backup" }
- s3: { "bucket": "ester-backups", "prefix": "releases/", "region": "eu-west-1",
            "endpoint_url": "https://s3.amazonaws.com", "access_key": "...", "secret_key": "..." }
          (esli access/secret otsutstvuyut — budut vzyaty iz okruzheniya AWS_* ili profilya)
- webdav: { "url": "https://webdav.example.com/ester", "username": "...", "password": "..." }
- email: { "smtp_host": "smtp.example.com", "smtp_port": 587, "use_tls": true,
            "username": "ester@example.com", "password": "...", "from": "ester@example.com",
            "to": ["owner@example.com"] }

ENV:
  PERSIST_DIR — koren dannykh (po umolchaniyu ./data)
  ESTER_STORAGE_ALLOWLIST — cherez ":" spisok korney, kuda mozhno pisat lokalno (dop. zaschita)"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGETS_REL = os.path.join("self", "targets.json")


def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    return base


def _targets_path() -> str:
    return os.path.join(_persist_dir(), TARGETS_REL)


def _load_raw() -> Dict[str, Any]:
    p = _targets_path()
    if not os.path.exists(p):
        return {"version": 1, "targets": []}
    try:
        return json.load(open(p, "r", encoding="utf-8"))
    except Exception:
        return {"version": 1, "targets": []}


def _save_raw(obj: Dict[str, Any]) -> None:
    p = _targets_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def list_targets(include_disabled: bool = True) -> List[Dict[str, Any]]:
    raw = _load_raw()
    items = raw.get("targets", [])
    if include_disabled:
        return items
    return [t for t in items if t.get("enabled", True)]


def get_target(tid: str) -> Optional[Dict[str, Any]]:
    for t in list_targets(include_disabled=True):
        if t.get("id") == tid:
            return t
    return None


def add_target(t: Dict[str, Any]) -> Dict[str, Any]:
    if "id" not in t:
        t["id"] = f"t_{int(time.time()*1000)}"
    if "created" not in t:
        t["created"] = float(time.time())
    if "enabled" not in t:
        t["enabled"] = True
    raw = _load_raw()
    raw["targets"] = [x for x in raw.get("targets", []) if x.get("id") != t["id"]] + [t]
    _save_raw(raw)
    return {"ok": True, "id": t["id"], "target": t}


def update_target(tid: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    raw = _load_raw()
    updated = None
    out = []
    for x in raw.get("targets", []):
        if x.get("id") == tid:
            x2 = {**x, **patch}
            updated = x2
            out.append(x2)
        else:
            out.append(x)
    raw["targets"] = out
    _save_raw(raw)
    return {"ok": True, "target": updated}


def remove_target(tid: str) -> Dict[str, Any]:
    raw = _load_raw()
    old = raw.get("targets", [])
    new = [x for x in old if x.get("id") != tid]
    raw["targets"] = new
    _save_raw(raw)
    return {"ok": True, "removed": len(old) - len(new)}


def _allowlist() -> List[str]:
    raw = os.getenv("ESTER_STORAGE_ALLOWLIST", "").strip()
    return [p for p in raw.split(":") if p.strip()] if raw else []


def _linux_mounts() -> List[Tuple[str, str]]:
    res: List[Tuple[str, str]] = []
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 3:
                    res.append((parts[1], parts[2]))
    except Exception:
        pass
    return res


def discover_local_writable(min_free_mb: int = 256) -> List[str]:
    """Finds directories where you can probably write (home, /tnt, /media, /srv, etc.)
    Filters by allowlist, if specified."""
    cands: List[str] = []
    home = os.path.expanduser("~")
    for base in (
        home,
        "/mnt",
        "/media",
        "/srv",
        "/var",
        "/tmp",
        "/run/media",
        "/Volumes",
    ):
        if os.path.isdir(base):
            cands.append(base)

    for mnt, _fstype in _linux_mounts():
        if os.path.isdir(mnt):
            cands.append(mnt)

    # normalizuem i filtruem ochevidnyy musor
    uniq: List[str] = []
    seen = set()
    for p in cands:
        ap = os.path.abspath(p)
        if ap not in seen and os.path.isdir(ap) and os.access(ap, os.W_OK):
            seen.add(ap)
            uniq.append(ap)

    # allowlist (if specified, only prefixes from it)
    allow = _allowlist()
    if allow:
        uniq = [
            p
            for p in uniq
            if any(ap.startswith(os.path.abspath(a)) for a in allow)
            for ap in [os.path.abspath(p)]
        ]

    # check free space
    ok: List[str] = []
    for p in uniq:
        try:
            st = os.statvfs(p)
            free_mb = (st.f_bavail * st.f_frsize) / (1024 * 1024)
            if free_mb >= min_free_mb:
                ok.append(p)
        except Exception:
            continue
# return sorted(ok)