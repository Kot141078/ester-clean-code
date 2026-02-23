# -*- coding: utf-8 -*-
"""
Smoke bootstrap for timeline from scroll JSONL.

MOSTY:
- Yavnyy: scroll tail -> store bootstrap -> timeline output.
- Skrytyy #1: infoteoriya -> proveryaem, chto poleznyy nedavniy kontekst ne teryaetsya posle restarta.
- Skrytyy #2: kibernetika -> obschiy API store/timeline vmesto pryamogo dostupa k vnutrennemu sostoyaniya.

ZEMNOY ABZATs:
Pokhozhe na progrev kesha posle perezapuska: berem khvost zhurnala i ubezhdaemsya, chto lenta snova zhivaya.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from modules.memory import store
from modules.memory.timeline import build_timeline


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_memory_timeline_bootstrap_from_scroll(tmp_path):
    now = int(time.time())
    scroll = tmp_path / "scroll.jsonl"

    rows = [
        {"id": "r1", "ts": now - 2 * 86400, "kind": "fact", "source": "scroll", "text": "old memory line"},
        {"id": "r2", "ts": now - 12 * 3600, "type": "fact", "source": "scroll", "text": "recent ocr memory"},
        {"id": "r3", "ts": now - 2 * 3600, "type": "fact", "source": "scroll", "text": "recent invoice memory"},
        {"id": "r4", "ts": now - 1800, "kind": "fact", "source": "scroll", "text": "latest memory line"},
    ]
    _write_jsonl(scroll, rows)
    with scroll.open("a", encoding="utf-8") as f:
        f.write("{broken json line\n")

    store.reset_for_tests(clear_disk=True, file_path=str(tmp_path / "memory_store.json"))
    rep = store.load_recent_from_scroll([str(scroll)], max_lines=100)

    assert rep["ok"] is True
    assert rep["loaded"] >= 4
    assert rep["read_lines"] >= 4

    all_tl = build_timeline(start_ts=None, end_ts=None, type_=None, source="scroll", q=None, limit=100, offset=0)
    assert all_tl["ok"] is True
    assert all_tl["total"] >= 4

    start_ts = now - 86400
    recent_tl = build_timeline(
        start_ts=start_ts,
        end_ts=None,
        type_=None,
        source="scroll",
        q=None,
        limit=100,
        offset=0,
    )
    assert recent_tl["total"] >= 3
