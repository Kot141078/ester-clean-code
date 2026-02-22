# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from modules.runtime import comm_window
from modules.volition.volition_gate import VolitionContext, get_default_gate

_LOCK = threading.RLock()
_SLOTB_DISABLED = False
_TELEGRAM_HOST = "api.telegram.org"


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _slot() -> str:
    v = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if v == "B" else "A"


def _network_enabled_env() -> bool:
    return _truthy(os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")) or _truthy(os.getenv("ESTER_ALLOW_NETWORK", "0"))


def _rollback_slot_a(reason: str) -> None:
    global _SLOTB_DISABLED
    with _LOCK:
        _SLOTB_DISABLED = True
    os.environ["ESTER_VOLITION_SLOT"] = "A"
    os.environ["ESTER_TELEGRAM_SENDER_LAST_ROLLBACK_REASON"] = str(reason or "telegram_sender_policy_violation")


def _default_dry_run() -> bool:
    # Offline-first.
    return True


def _policy_check(
    *,
    window_id: str,
    reason: str,
    chat_id: str,
    gate: Any,
    budgets: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if _slot() != "B":
        return {"ok": False, "error": "comm_denied", "reason": "slot_a_local_only", "network_attempted": False}
    with _LOCK:
        if _SLOTB_DISABLED:
            return {"ok": False, "error": "comm_denied", "reason": "slot_b_disabled_in_process", "network_attempted": False}
    if not _network_enabled_env():
        return {"ok": False, "error": "comm_denied", "reason": "outbound_network_disabled", "network_attempted": False}

    win = comm_window.is_open(window_id)
    if not bool(win.get("open")):
        return {"ok": False, "error": "comm_denied", "reason": "comm_window_closed", "network_attempted": False}
    wobj = dict(win.get("window") or {})
    if str(wobj.get("kind") or "") != "telegram":
        _rollback_slot_a("comm_window_kind_mismatch")
        return {"ok": False, "error": "comm_denied", "reason": "comm_window_kind_mismatch", "network_attempted": False}
    hosts = [str(x).strip().lower() for x in list(wobj.get("allow_hosts") or []) if str(x).strip()]
    if _TELEGRAM_HOST not in hosts:
        _rollback_slot_a("telegram_host_not_allowed")
        return {"ok": False, "error": "comm_denied", "reason": "telegram_host_not_allowed", "network_attempted": False}

    ctx = VolitionContext(
        chain_id="chain_comm_" + str(window_id or ""),
        step="action",
        actor="agent:companion",
        intent=str(reason or "telegram_send"),
        action_kind="messages.telegram.send",
        needs=["network", "comm"],
        budgets=dict(budgets or {"max_actions": 1, "max_work_ms": 2000, "window": 60, "est_work_ms": 350}),
        metadata={"window_id": str(window_id or ""), "chat_id": str(chat_id or "")},
    )
    dec = gate.decide(ctx)
    if not bool(dec.allowed):
        _rollback_slot_a(f"volition_denied:{dec.reason_code}")
        return {
            "ok": False,
            "error": "comm_denied",
            "reason": dec.reason,
            "reason_code": dec.reason_code,
            "slot": dec.slot,
            "network_attempted": False,
        }
    return {"ok": True, "volition": dec.to_dict(), "network_attempted": False}


def send(
    text: str,
    chat_id: Any,
    window_id: str,
    reason: str,
    dry_run: Optional[bool] = None,
    gate: Any = None,
    budgets: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if gate is None:
        gate = get_default_gate()
    msg_text = str(text or "").strip()
    cid = str(chat_id or "").strip()
    wid = str(window_id or "").strip()
    if not msg_text:
        return {"ok": False, "error": "text_required", "network_attempted": False}
    if not cid:
        return {"ok": False, "error": "chat_id_required", "network_attempted": False}
    if not wid:
        return {"ok": False, "error": "window_id_required", "network_attempted": False}

    chk = _policy_check(window_id=wid, reason=str(reason or ""), chat_id=cid, gate=gate, budgets=budgets)
    if not bool(chk.get("ok")):
        return chk

    use_dry = _default_dry_run() if dry_run is None else bool(dry_run)
    if use_dry:
        return {
            "ok": True,
            "dry_run": True,
            "chat_id": cid,
            "provider": "telegram_sender",
            "network_attempted": False,
            "volition": chk.get("volition"),
        }

    token = str(os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN") or "").strip()
    if not token:
        return {
            "ok": False,
            "error": "telegram_token_missing",
            "network_attempted": False,
            "volition": chk.get("volition"),
        }

    url = f"https://{_TELEGRAM_HOST}/bot{token}/sendMessage"
    body = json.dumps({"chat_id": cid, "text": msg_text}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    timeout = max(1, int(os.getenv("TELEGRAM_TIMEOUT_SEC", "10") or "10"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return {
            "ok": True,
            "dry_run": False,
            "chat_id": cid,
            "provider": "telegram_sender",
            "network_attempted": True,
            "result": raw[:2000],
            "volition": chk.get("volition"),
        }
    except urllib.error.HTTPError as exc:
        _rollback_slot_a(f"telegram_http_error:{int(exc.code)}")
        return {
            "ok": False,
            "error": "telegram_http_error",
            "status": int(exc.code),
            "network_attempted": True,
            "volition": chk.get("volition"),
        }
    except Exception as exc:
        _rollback_slot_a("telegram_send_exception")
        return {
            "ok": False,
            "error": "telegram_send_exception",
            "detail": exc.__class__.__name__,
            "network_attempted": True,
            "volition": chk.get("volition"),
        }


__all__ = ["send"]

