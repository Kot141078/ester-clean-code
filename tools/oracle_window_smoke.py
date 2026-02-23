# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.llm import providers_openai_oracle
from modules.runtime import oracle_window


def main() -> int:
    os.environ["ESTER_ORACLE_DRY_RUN_DISABLE"] = "0"
    os.environ["ESTER_ORACLE_ENABLE"] = "1"
    providers_openai_oracle.reset_slot_b_fallback()

    cur = oracle_window.current_window()
    if bool(cur.get("open")) and str(cur.get("window_id") or "").strip():
        oracle_window.close_window(str(cur.get("window_id") or ""), actor="ester:smoke", reason="reset")

    # case 1: no window => denied
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "1"
    c1 = providers_openai_oracle.call(
        prompt="ping",
        model="gpt-4o-mini",
        window_id="",
        reason="oracle_window_smoke:no_window",
        dry_run=True,
    )

    opened = oracle_window.open_window(kind="openai", ttl_sec=10, reason="oracle_window_smoke", actor="ester:smoke")
    window_id = str(opened.get("window_id") or "")

    # case 2: slot A with window => denied
    os.environ["ESTER_VOLITION_SLOT"] = "A"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "1"
    c2 = providers_openai_oracle.call(
        prompt="ping",
        model="gpt-4o-mini",
        window_id=window_id,
        reason="oracle_window_smoke:slot_a",
        dry_run=True,
    )

    # case 3: slot B + open window => allowed in dry-run
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "1"
    c3 = providers_openai_oracle.call(
        prompt="ping",
        model="gpt-4o-mini",
        window_id=window_id,
        reason="oracle_window_smoke:allowed_dry",
        dry_run=True,
    )

    # case 4: slot B + outbound disabled + non-dry-run => denied before network
    os.environ["ESTER_VOLITION_SLOT"] = "B"
    os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = "0"
    c4 = providers_openai_oracle.call(
        prompt="ping",
        model="gpt-4o-mini",
        window_id=window_id,
        reason="oracle_window_smoke:no_outbound",
        dry_run=False,
    )

    close_rep = oracle_window.close_window(window_id)

    ok = (
        (not bool(c1.get("ok")))
        and (str(c1.get("error")) == "oracle_window_closed")
        and (not bool(c1.get("network_attempted")))
        and (not bool(c2.get("ok")))
        and (str(c2.get("error")) == "oracle_slot_closed")
        and (not bool(c2.get("network_attempted")))
        and bool(c3.get("ok"))
        and bool(c3.get("dry_run"))
        and (not bool(c3.get("network_attempted")))
        and (not bool(c4.get("ok")))
        and (str(c4.get("error")) == "outbound_network_disabled")
        and (not bool(c4.get("network_attempted")))
        and bool(close_rep.get("ok"))
    )

    out = {
        "ok": ok,
        "no_window": c1,
        "slot_a_denied": c2,
        "slot_b_with_window_allowed": c3,
        "no_outbound_denied": c4,
        "close_window": close_rep,
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    old_slot = os.environ.get("ESTER_VOLITION_SLOT")
    old_net = os.environ.get("ESTER_ALLOW_OUTBOUND_NETWORK")
    old_dry = os.environ.get("ESTER_ORACLE_DRY_RUN_DISABLE")
    old_oracle = os.environ.get("ESTER_ORACLE_ENABLE")
    old_hours = os.environ.get("ESTER_VOLITION_ALLOWED_HOURS")
    os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = "00:00-23:59"
    try:
        raise SystemExit(main())
    finally:
        if old_slot is None:
            os.environ.pop("ESTER_VOLITION_SLOT", None)
        else:
            os.environ["ESTER_VOLITION_SLOT"] = old_slot
        if old_net is None:
            os.environ.pop("ESTER_ALLOW_OUTBOUND_NETWORK", None)
        else:
            os.environ["ESTER_ALLOW_OUTBOUND_NETWORK"] = old_net
        if old_dry is None:
            os.environ.pop("ESTER_ORACLE_DRY_RUN_DISABLE", None)
        else:
            os.environ["ESTER_ORACLE_DRY_RUN_DISABLE"] = old_dry
        if old_oracle is None:
            os.environ.pop("ESTER_ORACLE_ENABLE", None)
        else:
            os.environ["ESTER_ORACLE_ENABLE"] = old_oracle
        if old_hours is None:
            os.environ.pop("ESTER_VOLITION_ALLOWED_HOURS", None)
        else:
            os.environ["ESTER_VOLITION_ALLOWED_HOURS"] = old_hours
