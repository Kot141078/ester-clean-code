# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.channels import telegram_sender
from modules.runtime import comm_window


def main() -> int:
    old_slot = os.environ.get("ESTER_VOLITION_SLOT")
    old_net = os.environ.get("ESTER_ALLOW_OUTBOUND_NETWORK")
    old_hours = os.environ.get("ESTER_VOLITION_ALLOWED_HOURS")
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "1"
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"

    try:
        no_window = telegram_sender.send(
            text="smoke",
            chat_id="123456",
            window_id="",
            reason="telegram_sender_smoke:no_window",
            dry_run=True,
        )

        opened = comm_window.open_window(
            kind="telegram",
            ttl_sec=10,
            reason="telegram_sender_smoke",
            allow_hosts=["api.telegram.org"],
        )
        wid = str(opened.get("window_id") or "")
        with_window = telegram_sender.send(
            text="smoke",
            chat_id="123456",
            window_id=wid,
            reason="telegram_sender_smoke:with_window",
            dry_run=None,  # default dry-run expected
        )
        closed = comm_window.close_window(wid)

        ok = (
            (not bool(no_window.get("ok")))
            and (str(no_window.get("error") or "").endswith("denied") or str(no_window.get("error") or "") == "window_id_required")
            and (not bool(no_window.get("network_attempted")))
            and bool(with_window.get("ok"))
            and bool(with_window.get("dry_run"))
            and (not bool(with_window.get("network_attempted")))
            and bool(closed.get("ok"))
        )
        out = {
            "ok": ok,
            "no_window": no_window,
            "open_window": opened,
            "with_window_default_dry_run": with_window,
            "close_window": closed,
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        if old_slot is None:
            os.environ.pop("ESTER_VOLITION_SLOT", None)
        else:
            os.environ["ESTER_VOLITION_SLOT"] = old_slot
        if old_net is None:
            os.environ.pop("ESTER_ALLOW_OUTBOUND_NETWORK", None)
        else:
            os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = old_net
        if old_hours is None:
            os.environ.pop("ESTER_VOLITION_ALLOWED_HOURS", None)
        else:
            os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = old_hours


if __name__ == "__main__":
    raise SystemExit(main())

