
# -*- coding: utf-8 -*-
from __future__ import annotations
"""modules.media.progress - faylovyy agregator sobytiy (atomarno).
Mosty:
- Yavnyy: record_event()/summary() — tsentralizovannyy uchet obrabotki.
- Skrytyy #1: (DX ↔ Nadezhnost) — atomarnaya zapis JSON; zhurnal ogranichen N sobytiyami.
- Skrytyy #2: (Integratsiya ↔ Otchety) — prostaya svodka dlya HTTP‑paneley.

Zemnoy abzats:
Eto kak zhurnal nablyudeniy: kto, chto i kogda obrabotal. Deshevo i serdito, no dostatochno dlya kontrolya potoka.
# c=a+b"""
import os, json, time, tempfile
from pathlib import Path
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MAX_EVENTS = int(os.getenv("ESTER_MEDIA_MAX_EVENTS","500"))

def _path() -> Path:
    p = Path("data/media/progress.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(json.dumps({"events": [], "counters": {}}, ensure_ascii=False), encoding="utf-8")
    return p

def _load() -> Dict[str, Any]:
    p = _path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"events": [], "counters": {}}

def _store(data: Dict[str, Any]) -> None:
    p = _path()
    fd, tmp = tempfile.mkstemp(prefix="progress_", suffix=".json", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass

def record_event(src: str, status: str, meta: Dict[str, Any]) -> None:
    data = _load()
    ev = {"ts": int(time.time()), "src": src, "status": status, "meta": meta}
    data["events"].append(ev)
    # clip
    if len(data["events"]) > MAX_EVENTS:
        data["events"] = data["events"][-MAX_EVENTS:]
    # counters
    cnt = data.setdefault("counters", {})
    cnt[status] = int(cnt.get(status, 0)) + 1
    _store(data)

def summary() -> Dict[str, Any]:
    data = _load()
    return {
        "ok": True,
        "events_total": len(data.get("events", [])),
        "counters": data.get("counters", {}),
        "last": data.get("events", [])[-5:],
    }