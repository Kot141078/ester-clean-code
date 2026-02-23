# -*- coding: utf-8 -*-
"""
listeners/projects_inbox.py — avto-podkhvat proektov/zadaniy iz drop-folder.

Povedenie (pri PROJECTS_INBOX_ENABLE=1):
  • Raz v PROJECTS_INBOX_POLL sekund chitaet {ESTER_STATE_DIR}/inbox/projects/.
  • Dlya *.json: ozhidaetsya {"name": "...", "jobs":[{"prompt": "..."}], "defaults":{...}} — sozdaet proekt i perenosit fayl v processed/.
  • Dlya *.txt: kazhdaya nepustaya stroka = zadanie; imya proekta = imya fayla; sozdaet proekt, dobavlyaet zadaniya; perenosit fayl v processed/.
  • Bezopasno: esli parsing padaet — fayl perenositsya v failed/ s kommentariem.

AB-zamechanie: sozdanie faylov proekta ne izmenyaet yadro Ester; opasnykh deystviy net.

Mosty:
- Yavnyy (UX ↔ Ekspluatatsiya): faylopapka kak «bumazhnyy yaschik» dlya zadach.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): vse validiruetsya i protokoliruetsya cherez faylovuyu strukturu processed/failed.
- Skrytyy 2 (Praktika ↔ Sovmestimost): perenosimye tekst/JSON formaty.

Zemnoy abzats:
Eto «yaschik vkhodyaschikh»: polozhil fayl — poluchil proekt; udobno offlayn i dlya massovykh puskov.

# c=a+b
"""
from __future__ import annotations
import argparse, json, os, shutil, time
from pathlib import Path
from typing import Any, Dict, List

from modules.projects.project_store import ensure_inbox, create_project, add_jobs  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _move(p: Path, sub: str) -> None:
    dest = p.parent / sub; dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(p), str(dest / p.name))

def _handle_json(p: Path) -> None:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        name = str(d.get("name") or p.stem)
        defaults = d.get("defaults") or None
        jobs = d.get("jobs") or []
        if not jobs: raise ValueError("empty jobs")
        rep = create_project(name, defaults)
        if not rep.get("ok"): raise ValueError("create failed")
        pid = rep["id"]
        items = [{"prompt": str(j.get("prompt","")), "alias": j.get("alias"), "req": j.get("req",{}), "max_tokens": int(j.get("max_tokens",64)), "temperature": float(j.get("temperature",0.0))} for j in jobs]
        add_jobs(pid, items)
        _move(p, "processed")
    except Exception:
        _move(p, "failed")

def _handle_txt(p: Path) -> None:
    try:
        lines = [x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        if not lines: raise ValueError("empty file")
        rep = create_project(p.stem, None)
        if not rep.get("ok"): raise ValueError("create failed")
        pid = rep["id"]
        items = [{"prompt": ln, "max_tokens": 64, "temperature": 0.0} for ln in lines]
        add_jobs(pid, items)
        _move(p, "processed")
    except Exception:
        _move(p, "failed")

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester Projects Inbox")
    ap.add_argument("--loop", action="store_true")
    args = ap.parse_args(argv)

    if not bool(int(os.getenv("PROJECTS_INBOX_ENABLE","0"))):
        print("[projects-inbox] disabled", flush=True)
        return 0
    inbox = Path(ensure_inbox().get("path","."))
    poll = max(2, int(os.getenv("PROJECTS_INBOX_POLL","5")))
    try:
        while True:
            for p in inbox.glob("*.*"):
                if p.is_dir(): continue
                if p.suffix.lower()==".json": _handle_json(p)
                elif p.suffix.lower()==".txt": _handle_txt(p)
            if not args.loop: break
            time.sleep(poll)
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b