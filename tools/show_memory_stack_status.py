# -*- coding: utf-8 -*-
"""tools/show_memory_stack_status.py - offline memory stack status.

MOSTY:
- Yavnyy: profile/anchor/scroll -> edinaya diagnostika sostoyaniya pamyati.
- Skrytyy #1: infoteoriya -> meryaem, est li poleznyy signal (ne pustye fayly), a ne tolko fakt nalichiya putey.
- Skrytyy #2: kibernetika -> odin status-layer dlya bootstrap i timeline umenshaet rassoglasovanie konturov.

ZEMNOY ABZATs:
Eto kak pribornaya panel u kesha: vidno, est li bazovye opory i skolko nedavnikh strok mozhno podnyat v pamyat."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.memory.scroll_reader import read_jsonl_tail


def _split_paths(raw: str) -> List[str]:
    s = str(raw or "").strip()
    if not s:
        return []
    return [x.strip() for x in s.replace("\n", ";").split(";") if x.strip()]


def _file_info(path: Path) -> Dict[str, Any]:
    exists = path.exists()
    size = int(path.stat().st_size) if exists and path.is_file() else 0
    non_empty = bool(exists and path.is_file() and size > 0)
    return {"path": str(path), "exists": bool(exists), "size": size, "non_empty": non_empty}


def _candidate_scrolls() -> List[Path]:
    out: List[Path] = []
    for p in _split_paths(os.getenv("ESTER_SCROLL_PATH", "")):
        out.append(Path(p))
    out.append(ROOT / "data" / "passport" / "clean_memory.jsonl")
    out.append(ROOT / "data" / "memory" / "events.jsonl")

    uniq: List[Path] = []
    seen = set()
    for p in out:
        rp = p.resolve()
        if str(rp) in seen:
            continue
        seen.add(str(rp))
        uniq.append(rp)
    return uniq


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-lines", type=int, default=2000, help="How many tail lines to read from each scroll JSONL.")
    args = ap.parse_args(argv)

    core_facts = ROOT / "data" / "passport" / "core_facts.txt"
    anchor = ROOT / "data" / "passport" / "anchor.txt"

    out: Dict[str, Any] = {
        "ok": True,
        "core_facts": _file_info(core_facts),
        "anchor": _file_info(anchor),
        "scrolls": [],
    }

    for p in _candidate_scrolls():
        item: Dict[str, Any] = {"path": str(p), "exists": p.exists(), "read_lines": 0}
        if p.exists() and p.is_file():
            rows = read_jsonl_tail(str(p), max_lines=max(1, int(args.max_lines or 2000)))
            item["read_lines"] = len(rows)
        out["scrolls"].append(item)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
