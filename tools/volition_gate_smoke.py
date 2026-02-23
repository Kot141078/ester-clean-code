# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.volition.volition_gate import VolitionContext, get_default_gate
from modules.ops import control_state as ops_control_state


def _set_env(k: str, v: str) -> str | None:
    old = os.environ.get(k)
    os.environ[k] = v
    return old


def _restore_env(k: str, old: str | None) -> None:
    if old is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = old


def main() -> int:
    gate = get_default_gate()
    old_slot = _set_env("ESTER_VOLITION_SLOT", "A")
    old_allow_net = _set_env("ESTER_ALLOW_NETWORK", "0")
    old_hours = _set_env("ESTER_VOLITION_ALLOWED_HOURS", "00:00-23:59")

    try:
        d_a = gate.decide(
            VolitionContext(
                chain_id="smoke_slot_a",
                step="action",
                actor="agent:smoke",
                intent="slot_a_observe",
                action_kind="smoke.network",
                needs=["network"],
            )
        )
        cond_a = bool(d_a.allowed)

        os.environ["ESTER_VOLITION_SLOT"] = "B"
        d_b_net = gate.decide(
            VolitionContext(
                chain_id="smoke_slot_b_network",
                step="action",
                actor="agent:smoke",
                intent="slot_b_network_deny",
                action_kind="smoke.network",
                needs=["network"],
            )
        )
        cond_b_net = (not d_b_net.allowed) and (d_b_net.reason_code in {"DENY_NETWORK", "DENY_BUDGET", "DENY_PAUSED"})

        ops_control_state.set_paused(True)
        d_b_paused = gate.decide(
            VolitionContext(
                chain_id="smoke_slot_b_paused",
                step="plan",
                actor="ester",
                intent="slot_b_paused_check",
                needs=["proactivity.plan"],
            )
        )
        ops_control_state.set_paused(False)
        cond_b_paused = (not d_b_paused.allowed) and (d_b_paused.reason_code == "DENY_PAUSED")

        ok = cond_a and cond_b_net and cond_b_paused
        out = {
            "ok": ok,
            "slot_a": d_a.to_dict(),
            "slot_b_network": d_b_net.to_dict(),
            "slot_b_paused": d_b_paused.to_dict(),
            "checks": {
                "slot_a_allowed": cond_a,
                "slot_b_network_denied": cond_b_net,
                "slot_b_paused_denied": cond_b_paused,
            },
        }
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0 if ok else 2
    finally:
        try:
            ops_control_state.set_paused(False)
        except Exception:
            pass
        _restore_env("ESTER_VOLITION_SLOT", old_slot)
        _restore_env("ESTER_ALLOW_NETWORK", old_allow_net)
        _restore_env("ESTER_VOLITION_ALLOWED_HOURS", old_hours)


if __name__ == "__main__":
    raise SystemExit(main())
