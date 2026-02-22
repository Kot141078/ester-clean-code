# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any, Dict, List, Tuple

from modules.volition.volition_gate import VolitionContext, get_default_gate

COST_AB = (os.getenv("COST_AB", "A") or "A").upper()
DB = os.getenv("COST_DB", "data/ops/cost_fence.json")
LEDGER = os.getenv("COST_LEDGER", "data/ops/cost_ledger.jsonl")
REFILL_SEC = int(os.getenv("COST_REFILL_SEC", "86400") or "86400")
DEF_BUDGET = float(os.getenv("COST_DEFAULT_BUDGET", "10.0") or "10.0")
L_LLM_PER_ACT = float(os.getenv("COST_LLM_MAX_PER_ACT", "1.0") or "1.0")
L_WEB_PER_ACT = float(os.getenv("COST_WEB_MAX_PER_ACT", "0.2") or "0.2")
PEERS = [p.strip() for p in str(os.getenv("PEERS", "") or "").split(",") if p.strip()]
CRON_MAX_AGE_DAYS = int(os.getenv("CRON_MAX_AGE_DAYS", "30") or "30")
WEBHOOK_URL = (os.getenv("WEBHOOK_URL", "") or "").strip()
MONITOR_THRESHOLD = float(os.getenv("MONITOR_THRESHOLD", "1.0") or "1.0")

_state: Dict[str, Any] = {
    "updated": 0,
    "last_cleanup": int(time.time()),
    "budgets": {},
    "usage": {},
}


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _network_env_allowed() -> bool:
    return _truthy(os.getenv("ESTER_ALLOW_NETWORK", "0")) or _truthy(
        os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")
    )


def _allow_network_call(target: str, purpose: str, meta: Dict[str, Any] | None = None) -> Tuple[bool, Dict[str, Any]]:
    gate = get_default_gate()
    dec = gate.decide(
        VolitionContext(
            chain_id="cost_fence_network",
            step="action",
            actor="agent:cost_fence",
            intent=purpose,
            action_kind=purpose,
            needs=["network"],
            budgets={},
            metadata={"target": str(target), **dict(meta or {})},
        )
    )
    if dec.slot == "B" and not dec.allowed:
        return False, {
            "ok": False,
            "error": "volition_denied",
            "reason_code": dec.reason_code,
            "reason": dec.reason,
            "slot": dec.slot,
            "target": str(target),
        }
    if not _network_env_allowed():
        return False, {
            "ok": False,
            "error": "network_denied",
            "reason": "closed_box_default_deny",
            "target": str(target),
        }
    return True, {"ok": True}


def _ensure() -> None:
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    if not os.path.isfile(DB):
        default = {
            "updated": int(time.time()),
            "last_cleanup": int(time.time()),
            "budgets": {
                "llm": {"daily": 1.0, "monthly": 20.0, "per_act": L_LLM_PER_ACT},
                "web": {"daily": 0.5, "monthly": 10.0, "per_act": L_WEB_PER_ACT},
                "default": {"daily": DEF_BUDGET, "monthly": DEF_BUDGET * 30, "per_act": 0.25},
            },
            "usage": {},
        }
        with open(DB, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
    if not os.path.isfile(LEDGER):
        open(LEDGER, "a", encoding="utf-8").close()


def _load() -> None:
    _ensure()
    try:
        with open(DB, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}

    _state["updated"] = int(raw.get("updated") or _state["updated"] or 0)
    _state["last_cleanup"] = int(raw.get("last_cleanup") or _state["last_cleanup"] or int(time.time()))
    _state["budgets"] = dict(raw.get("budgets") or {})
    _state["usage"] = dict(raw.get("usage") or {})

    if not _state["budgets"]:
        _state["budgets"] = {
            "llm": {"daily": 1.0, "monthly": 20.0, "per_act": L_LLM_PER_ACT},
            "web": {"daily": 0.5, "monthly": 10.0, "per_act": L_WEB_PER_ACT},
            "default": {"daily": DEF_BUDGET, "monthly": DEF_BUDGET * 30, "per_act": 0.25},
        }


def _save(sync_peers: bool = True) -> None:
    _state["updated"] = int(time.time())
    payload = {
        "updated": int(_state.get("updated") or 0),
        "last_cleanup": int(_state.get("last_cleanup") or int(time.time())),
        "budgets": dict(_state.get("budgets") or {}),
        "usage": dict(_state.get("usage") or {}),
    }
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    if sync_peers:
        sync_with_peers()


def _bucket(now: float, win: int) -> int:
    return int(now // max(1, int(win)) * max(1, int(win)))


def _ymd(ts: int) -> Tuple[str, str]:
    import datetime as dt

    d = dt.datetime.utcfromtimestamp(int(ts))
    return d.strftime("%Y-%m-%d"), d.strftime("%Y-%m")


def cron_cleanup() -> Dict[str, Any]:
    _load()
    now = int(time.time())
    removed = 0
    if now - int(_state.get("last_cleanup") or 0) >= 86400:
        keep: Dict[str, Any] = {}
        for key, value in dict(_state.get("usage") or {}).items():
            head = str(key).split(":", 1)[0]
            try:
                ts_key = int(head)
            except Exception:
                ts_key = 0
            age_days = (now - ts_key) / 86400.0 if ts_key > 0 else 9999.0
            if age_days <= float(CRON_MAX_AGE_DAYS):
                keep[key] = value
            else:
                removed += 1
        _state["usage"] = keep
        _state["last_cleanup"] = now
        _save(sync_peers=False)
    return {"ok": True, "cleanup_time": int(_state.get("last_cleanup") or now), "removed": int(removed)}


def config(
    refill_sec: int | None = None,
    default_budget: float | None = None,
    llm_per_act: float | None = None,
    web_per_act: float | None = None,
) -> Dict[str, Any]:
    global REFILL_SEC, DEF_BUDGET, L_LLM_PER_ACT, L_WEB_PER_ACT
    _load()
    if refill_sec is not None:
        REFILL_SEC = max(1, int(refill_sec))
    if default_budget is not None:
        DEF_BUDGET = max(0.0, float(default_budget))
    if llm_per_act is not None:
        L_LLM_PER_ACT = max(0.0, float(llm_per_act))
    if web_per_act is not None:
        L_WEB_PER_ACT = max(0.0, float(web_per_act))
    return {
        "ok": True,
        "refill_sec": REFILL_SEC,
        "default_budget": DEF_BUDGET,
        "llm_per_act": L_LLM_PER_ACT,
        "web_per_act": L_WEB_PER_ACT,
    }


def status() -> Dict[str, Any]:
    _load()
    cron_cleanup()

    today: Dict[str, Dict[str, float]] = {}
    month: Dict[str, Dict[str, float]] = {}
    try:
        with open(LEDGER, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    row = json.loads(s)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                cat = str(row.get("cat") or "default")
                amt = float(row.get("amount") or 0.0)
                d, m = _ymd(int(row.get("ts") or 0))
                today.setdefault(cat, {}).setdefault(d, 0.0)
                month.setdefault(cat, {}).setdefault(m, 0.0)
                today[cat][d] += amt
                month[cat][m] += amt
    except Exception:
        pass

    _d, m_now = _ymd(int(time.time()))
    report: Dict[str, Any] = {}
    budgets = dict(_state.get("budgets") or {})
    for cat, conf in budgets.items():
        conf = dict(conf or {})
        report[str(cat)] = {
            "daily_spent": float(sum(today.get(str(cat), {}).values())),
            "daily_limit": float(conf.get("daily") or DEF_BUDGET),
            "monthly_spent": float(month.get(str(cat), {}).get(m_now, 0.0)),
            "monthly_limit": float(conf.get("monthly") or (DEF_BUDGET * 30)),
            "per_act_limit": float(conf.get("per_act") or 0.25),
        }
    return {"ok": True, "report": report}


def set_budgets(budgets: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    _load()
    _state["budgets"] = dict(budgets or {})
    _save(sync_peers=False)
    return {"ok": True, **status()}


def evaluate(cat: str, amount: float) -> Dict[str, Any]:
    _load()
    cron_cleanup()

    if COST_AB == "B":
        # Backward-compatible behavior in this codebase: B disables hard budget rejects.
        return {"allow": True, "reason": "AB=B"}

    category = str(cat or "default").lower()
    amt = float(amount or 0.0)
    conf = dict(_state.get("budgets", {}).get(category) or _state.get("budgets", {}).get("default") or {})

    daily_limit = float(conf.get("daily") or DEF_BUDGET)
    monthly_limit = float(conf.get("monthly") or (DEF_BUDGET * 30))
    per_act_limit = float(conf.get("per_act") or 0.25)

    if amt > per_act_limit:
        return {"allow": False, "reason": "per_act_limit", "remain": max(0.0, per_act_limit)}

    now = time.time()
    day_key = f"{_bucket(now, REFILL_SEC)}:{category}:daily"
    month_key = f"{_bucket(now, max(REFILL_SEC, 86400 * 30))}:{category}:monthly"

    d_used = float(_state.get("usage", {}).get(day_key, 0.0))
    m_used = float(_state.get("usage", {}).get(month_key, 0.0))

    if d_used + amt > daily_limit:
        return {"allow": False, "reason": "daily_limit", "remain": max(0.0, daily_limit - d_used)}
    if m_used + amt > monthly_limit:
        return {"allow": False, "reason": "monthly_limit", "remain": max(0.0, monthly_limit - m_used)}

    return {"allow": True, "reason": "ok", "remain": max(0.0, min(daily_limit - d_used, monthly_limit - m_used))}


def sync_with_peers() -> Dict[str, Any]:
    _load()
    if not PEERS:
        return {"ok": True, "sent": [], "skipped": []}

    body = json.dumps({"budgets": _state.get("budgets", {}), "usage": _state.get("usage", {})}).encode("utf-8")
    sent: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for peer in PEERS:
        allow, info = _allow_network_call(peer, "cost_fence_peer_sync", {"peer": peer})
        if not allow:
            skipped.append({"peer": peer, **info})
            continue
        try:
            req = urllib.request.Request(peer, data=body, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5):  # nosec B310
                pass
            sent.append({"peer": peer, "ok": True})
        except Exception as exc:
            sent.append({"peer": peer, "ok": False, "error": str(exc)})

    return {"ok": True, "sent": sent, "skipped": skipped}


def receive_sync(payload: Dict[str, Any]) -> Dict[str, Any]:
    _load()
    p = dict(payload or {})

    for cat, data in dict(p.get("budgets") or {}).items():
        src = dict(data or {})
        if cat in _state["budgets"]:
            cur = dict(_state["budgets"][cat] or {})
            for key in ["daily", "monthly", "per_act"]:
                cur[key] = max(float(cur.get(key) or 0.0), float(src.get(key) or 0.0))
            _state["budgets"][cat] = cur
        else:
            _state["budgets"][cat] = src

    for key, spent in dict(p.get("usage") or {}).items():
        _state["usage"][str(key)] = float(_state["usage"].get(str(key), 0.0)) + float(spent or 0.0)

    _save(sync_peers=False)
    return {"ok": True, "budgets": len(_state.get("budgets") or {}), "usage": len(_state.get("usage") or {})}


def spend(cat: str, amount: float, currency: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    _load()
    amt = float(amount or 0.0)
    category = str(cat or "default").lower()
    decision = evaluate(category, amt)

    line = {
        "ts": int(time.time()),
        "cat": category,
        "amount": amt,
        "currency": str(currency or ""),
        "meta": dict(meta or {}),
        "decision": dict(decision or {}),
    }
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

    if bool(decision.get("allow")):
        now = time.time()
        day_key = f"{_bucket(now, REFILL_SEC)}:{category}:daily"
        month_key = f"{_bucket(now, max(REFILL_SEC, 86400 * 30))}:{category}:monthly"
        _state["usage"][day_key] = float(_state["usage"].get(day_key, 0.0)) + amt
        _state["usage"][month_key] = float(_state["usage"].get(month_key, 0.0)) + amt
        _save(sync_peers=True)

    webhook_attempted = False
    webhook_sent = False
    webhook_error = ""
    if WEBHOOK_URL and ((not bool(decision.get("allow"))) or amt > MONITOR_THRESHOLD):
        webhook_attempted = True
        allow, _ = _allow_network_call(WEBHOOK_URL, "cost_fence_webhook", {"category": category})
        if allow:
            try:
                alert = {
                    "cat": category,
                    "amount": amt,
                    "allow": bool(decision.get("allow")),
                    "ts": int(time.time()),
                }
                req = urllib.request.Request(
                    WEBHOOK_URL,
                    data=json.dumps(alert).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5):  # nosec B310
                    pass
                webhook_sent = True
            except Exception as exc:
                webhook_error = str(exc)
        else:
            webhook_error = "network_denied"

    out = {
        "ok": bool(decision.get("allow")),
        "decision": decision,
        "cat": category,
        "amount": amt,
        "currency": str(currency or ""),
        "webhook": {
            "attempted": webhook_attempted,
            "sent": webhook_sent,
            "error": webhook_error,
        },
    }
    return out


_load()
