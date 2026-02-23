# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.companion import outbox


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def main() -> int:
    mpath = outbox.messages_path()
    apath = outbox.acks_path()
    before_m = _count_lines(mpath)
    before_a = _count_lines(apath)

    enq = outbox.enqueue(
        kind="smoke.note",
        text="outbox_smoke message",
        meta={"tool": "outbox_smoke"},
        chain_id="chain_outbox_smoke",
        related_action="messages.outbox.enqueue",
    )
    rows = outbox.tail(5)
    ack = outbox.mark_delivered(str(enq.get("msg_id") or ""), "smoke")

    after_m = _count_lines(mpath)
    after_a = _count_lines(apath)

    ok = bool(enq.get("ok")) and bool(ack.get("ok")) and (after_m > before_m) and (after_a > before_a) and bool(rows)
    out = {
        "ok": ok,
        "enqueue": enq,
        "tail_count": len(rows),
        "mark_delivered": ack,
        "messages_lines_delta": after_m - before_m,
        "acks_lines_delta": after_a - before_a,
        "messages_path": str(mpath),
        "acks_path": str(apath),
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

