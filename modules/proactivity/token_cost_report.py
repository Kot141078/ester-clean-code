# -*- coding: utf-8 -*-
"""
LLM token/cost telemetry for proactive Telegram reporting.

Stores one JSONL record per successful LLM call and builds day/month summaries.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from typing import Any, Dict, Iterable, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - fallback for very old environments
    ZoneInfo = None  # type: ignore


def _env_float(name: str, default: float) -> float:
    try:
        raw = os.getenv(name, str(default))
        return float(raw if raw not in (None, "") else default)
    except Exception:
        return float(default)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on", "y"}


LEDGER_PATH = (
    os.getenv("ESTER_LLM_USAGE_LEDGER_PATH", "").strip()
    or os.path.join("data", "ops", "llm_usage_ledger.jsonl")
)
LEDGER_ENABLED = str(os.getenv("ESTER_LLM_USAGE_LEDGER_ENABLED", "1") or "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
    "y",
}
PROVIDER_TRACE_PATH = (
    os.getenv("ESTER_PROVIDER_TRACE_LEDGER_PATH", "").strip()
    or os.path.join("data", "ops", "provider_trace_ledger.jsonl")
)
PROVIDER_TRACE_ENABLED = _env_bool("ESTER_PROVIDER_TRACE_ENABLED", True)

# Cost rates are expressed in USD per 1M tokens.
OPENAI_IN_USD_PER_1M = _env_float("ESTER_LLM_COST_OPENAI_INPUT_USD_PER_1M", 0.25)
OPENAI_OUT_USD_PER_1M = _env_float("ESTER_LLM_COST_OPENAI_OUTPUT_USD_PER_1M", 2.0)
GEMINI_IN_USD_PER_1M = _env_float("ESTER_LLM_COST_GEMINI_INPUT_USD_PER_1M", 0.10)
GEMINI_OUT_USD_PER_1M = _env_float("ESTER_LLM_COST_GEMINI_OUTPUT_USD_PER_1M", 0.40)
LOCAL_IN_USD_PER_1M = _env_float("ESTER_LLM_COST_LOCAL_INPUT_USD_PER_1M", 0.0)
LOCAL_OUT_USD_PER_1M = _env_float("ESTER_LLM_COST_LOCAL_OUTPUT_USD_PER_1M", 0.0)
DEFAULT_IN_USD_PER_1M = _env_float("ESTER_LLM_COST_DEFAULT_INPUT_USD_PER_1M", 0.0)
DEFAULT_OUT_USD_PER_1M = _env_float("ESTER_LLM_COST_DEFAULT_OUTPUT_USD_PER_1M", 0.0)


def _to_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return int(default)
        return int(float(v))
    except Exception:
        return int(default)


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _safe_str(v: Any) -> str:
    try:
        return str(v or "").strip()
    except Exception:
        return ""


def _estimate_tokens_from_text(text: str) -> int:
    t = _safe_str(text)
    if not t:
        return 0
    return max(1, (len(t) + 3) // 4)


def _estimate_prompt_tokens(messages: Any) -> int:
    total_chars = 0
    if isinstance(messages, list):
        for m in messages:
            if not isinstance(m, dict):
                continue
            role = _safe_str(m.get("role"))
            content = _safe_str(m.get("content"))
            if not role and not content:
                continue
            total_chars += len(role) + len(content) + 8
    elif messages is not None:
        total_chars = len(_safe_str(messages))
    if total_chars <= 0:
        return 0
    return max(1, (total_chars + 3) // 4)


def _usage_to_dict(usage: Any) -> Dict[str, Any]:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    out: Dict[str, Any] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
        try:
            val = getattr(usage, key, None)
            if val is not None:
                out[key] = val
        except Exception:
            continue
    return out


def _normalize_provider(provider: str, model: str = "") -> str:
    p = _safe_str(provider).lower()
    m = _safe_str(model).lower()
    if p in {"local", "lmstudio"}:
        return "local"
    if p in {"gemini", "google"}:
        return "gemini"
    if p in {"gpt4", "gpt-5-mini", "openai", "oai", "gpt"}:
        return "openai"
    if p == "peer":
        return "peer"
    if "gemini" in m:
        return "gemini"
    if ("gpt-" in m) or ("openai" in m) or m.startswith("o1") or m.startswith("o3"):
        return "openai"
    return p or "unknown"


def _normalize_channel(channel: str) -> str:
    c = _safe_str(channel).lower()
    if c in {"web", "http"}:
        return "web"
    if c in {"tg", "telegram"}:
        return "telegram"
    if c in {"dream", "dreams", "background"}:
        return "dream"
    return c or "unknown"


def _provider_rates(provider: str) -> Tuple[float, float]:
    p = _normalize_provider(provider)
    if p == "openai":
        return OPENAI_IN_USD_PER_1M, OPENAI_OUT_USD_PER_1M
    if p == "gemini":
        return GEMINI_IN_USD_PER_1M, GEMINI_OUT_USD_PER_1M
    if p in {"local", "peer"}:
        return LOCAL_IN_USD_PER_1M, LOCAL_OUT_USD_PER_1M
    return DEFAULT_IN_USD_PER_1M, DEFAULT_OUT_USD_PER_1M


def _estimate_cost_usd(provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_rate, out_rate = _provider_rates(provider)
    return (max(0, int(prompt_tokens)) * in_rate + max(0, int(completion_tokens)) * out_rate) / 1_000_000.0


def _extract_usage_tokens(
    usage: Any,
    messages: Any,
    output_text: str,
) -> Tuple[int, int, int, bool]:
    """
    Returns: prompt_tokens, completion_tokens, total_tokens, usage_estimated
    """
    usage_dict = _usage_to_dict(usage)

    prompt = _to_int(
        usage_dict.get("prompt_tokens", usage_dict.get("input_tokens")),
        0,
    )
    completion = _to_int(
        usage_dict.get("completion_tokens", usage_dict.get("output_tokens")),
        0,
    )
    total = _to_int(usage_dict.get("total_tokens"), 0)

    usage_estimated = False

    if prompt <= 0:
        prompt = _estimate_prompt_tokens(messages)
        usage_estimated = True

    if completion <= 0 and total > prompt:
        completion = max(0, total - prompt)
    if completion <= 0:
        completion = _estimate_tokens_from_text(output_text)
        usage_estimated = True

    if total <= 0:
        total = max(0, prompt + completion)
        usage_estimated = True

    return max(0, prompt), max(0, completion), max(0, total), bool(usage_estimated)


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)


def _append_jsonl(path: str, row: Dict[str, Any]) -> None:
    _ensure_parent(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def record_safe_chat_call(
    *,
    provider: str,
    model: str,
    messages: Any,
    output_text: str,
    response_usage: Any = None,
    chat_id: Optional[int] = None,
    source: str = "safe_chat",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Best-effort usage logging. Never raises.
    """
    if not LEDGER_ENABLED:
        return {"ok": True, "skipped": True, "reason": "ledger_disabled"}

    prompt_tokens, completion_tokens, total_tokens, usage_estimated = _extract_usage_tokens(
        response_usage,
        messages,
        output_text,
    )

    provider_norm = _normalize_provider(provider, model=model)
    cost_usd = _estimate_cost_usd(provider_norm, prompt_tokens, completion_tokens)
    cost_estimated = True  # cost is derived from env rates, not from provider billing API

    row: Dict[str, Any] = {
        "ts": int(time.time()),
        "provider": provider_norm,
        "provider_raw": _safe_str(provider) or provider_norm,
        "model": _safe_str(model),
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "total_tokens": int(total_tokens),
        "cost_usd": float(cost_usd),
        "currency": "USD",
        "usage_estimated": bool(usage_estimated),
        "cost_estimated": bool(cost_estimated),
        "source": _safe_str(source) or "safe_chat",
        "chat_id": int(chat_id) if isinstance(chat_id, int) else None,
        "meta": dict(meta or {}),
    }

    try:
        _append_jsonl(LEDGER_PATH, row)
        return {"ok": True, "row": row}
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}", "row": row}


def record_provider_event(
    *,
    channel: str,
    provider: str,
    event: str,
    ok: bool,
    latency_ms: int = 0,
    error: str = "",
    model: str = "",
    source: str = "provider_event",
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Best-effort channel/provider telemetry.
    Event examples: attempt, success, timeout, failure, fallback_success.
    """
    if not PROVIDER_TRACE_ENABLED:
        return {"ok": True, "skipped": True, "reason": "provider_trace_disabled"}

    row: Dict[str, Any] = {
        "ts": int(time.time()),
        "channel": _normalize_channel(channel),
        "provider": _normalize_provider(provider, model=model),
        "provider_raw": _safe_str(provider) or _normalize_provider(provider, model=model),
        "model": _safe_str(model),
        "event": _safe_str(event) or "event",
        "ok": bool(ok),
        "latency_ms": max(0, _to_int(latency_ms, 0)),
        "error": _safe_str(error),
        "source": _safe_str(source) or "provider_event",
        "meta": dict(meta or {}),
    }
    try:
        _append_jsonl(PROVIDER_TRACE_PATH, row)
        return {"ok": True, "row": row}
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}", "row": row}


def _resolve_tz(tz_name: Optional[str]) -> dt.tzinfo:
    name = _safe_str(tz_name or os.getenv("ESTER_TZ", "UTC")) or "UTC"
    if ZoneInfo is None:
        return dt.timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:
        return dt.timezone.utc


def _iter_rows(path: str) -> Iterable[Dict[str, Any]]:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except Exception:
                continue
            if isinstance(row, dict):
                yield row


def _empty_bucket() -> Dict[str, Any]:
    return {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
    }


def _add_to_bucket(bucket: Dict[str, Any], row: Dict[str, Any]) -> None:
    bucket["calls"] = int(bucket.get("calls", 0)) + 1
    bucket["prompt_tokens"] = int(bucket.get("prompt_tokens", 0)) + _to_int(row.get("prompt_tokens"), 0)
    bucket["completion_tokens"] = int(bucket.get("completion_tokens", 0)) + _to_int(row.get("completion_tokens"), 0)
    bucket["total_tokens"] = int(bucket.get("total_tokens", 0)) + _to_int(row.get("total_tokens"), 0)
    bucket["cost_usd"] = float(bucket.get("cost_usd", 0.0)) + _to_float(row.get("cost_usd"), 0.0)


def summarize_usage(now_ts: Optional[float] = None, tz_name: Optional[str] = None) -> Dict[str, Any]:
    tz = _resolve_tz(tz_name)
    now = dt.datetime.fromtimestamp(float(now_ts or time.time()), tz=tz)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = day_start.replace(day=1)

    day_total = _empty_bucket()
    month_total = _empty_bucket()
    day_by_provider: Dict[str, Dict[str, Any]] = {}
    month_by_provider: Dict[str, Dict[str, Any]] = {}

    rows_seen = 0
    rows_day = 0
    rows_month = 0

    for row in _iter_rows(LEDGER_PATH) or []:
        rows_seen += 1
        ts = _to_int(row.get("ts"), 0)
        if ts <= 0:
            continue
        try:
            when = dt.datetime.fromtimestamp(float(ts), tz=tz)
        except Exception:
            continue
        provider = _normalize_provider(_safe_str(row.get("provider") or row.get("provider_raw")), _safe_str(row.get("model")))
        norm_row = dict(row)
        norm_row["provider"] = provider

        if when >= month_start:
            rows_month += 1
            _add_to_bucket(month_total, norm_row)
            month_by_provider.setdefault(provider, _empty_bucket())
            _add_to_bucket(month_by_provider[provider], norm_row)

            if when >= day_start:
                rows_day += 1
                _add_to_bucket(day_total, norm_row)
                day_by_provider.setdefault(provider, _empty_bucket())
                _add_to_bucket(day_by_provider[provider], norm_row)

    return {
        "ok": True,
        "ledger_path": LEDGER_PATH,
        "tz": str(getattr(tz, "key", None) or tz),
        "now_local": now.isoformat(),
        "day_date": day_start.strftime("%Y-%m-%d"),
        "month": month_start.strftime("%Y-%m"),
        "rows_seen": int(rows_seen),
        "rows_day": int(rows_day),
        "rows_month": int(rows_month),
        "day_total": day_total,
        "month_total": month_total,
        "day_by_provider": day_by_provider,
        "month_by_provider": month_by_provider,
    }


def summarize_provider_events(now_ts: Optional[float] = None, tz_name: Optional[str] = None) -> Dict[str, Any]:
    tz = _resolve_tz(tz_name)
    now = dt.datetime.fromtimestamp(float(now_ts or time.time()), tz=tz)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    rows_seen = 0
    rows_day = 0
    day_channels: Dict[str, Dict[str, int]] = {}

    for row in _iter_rows(PROVIDER_TRACE_PATH) or []:
        rows_seen += 1
        ts = _to_int(row.get("ts"), 0)
        if ts <= 0:
            continue
        try:
            when = dt.datetime.fromtimestamp(float(ts), tz=tz)
        except Exception:
            continue
        if when < day_start:
            continue
        rows_day += 1
        channel = _normalize_channel(_safe_str(row.get("channel")))
        event = _safe_str(row.get("event")) or "event"
        bucket = day_channels.setdefault(channel, {})
        bucket[event] = int(bucket.get(event, 0)) + 1

    return {
        "ok": True,
        "provider_trace_path": PROVIDER_TRACE_PATH,
        "day_date": day_start.strftime("%Y-%m-%d"),
        "rows_seen": int(rows_seen),
        "rows_day": int(rows_day),
        "day_channels": day_channels,
    }


def _fmt_money_usd(v: float) -> str:
    return f"${float(v or 0.0):.4f}"


def _fmt_provider_lines(block: Dict[str, Dict[str, Any]]) -> str:
    if not block:
        return "- dannykh net"
    items = sorted(block.items(), key=lambda kv: float((kv[1] or {}).get("cost_usd", 0.0)), reverse=True)
    out = []
    for provider, stats in items:
        out.append(
            f"- {provider}: calls={int(stats.get('calls', 0))}, "
            f"tokens={int(stats.get('total_tokens', 0))} "
            f"(in={int(stats.get('prompt_tokens', 0))}, out={int(stats.get('completion_tokens', 0))}),"
            f"cost={_fmt_money_usd(float(stats.get('cost_usd', 0.0)))}"
        )
    return "\n".join(out)


def format_telegram_report(summary: Dict[str, Any]) -> str:
    day_total = dict(summary.get("day_total") or {})
    month_total = dict(summary.get("month_total") or {})
    rows_day = int(summary.get("rows_day") or 0)
    rows_month = int(summary.get("rows_month") or 0)

    day_lines = _fmt_provider_lines(dict(summary.get("day_by_provider") or {}))
    month_lines = _fmt_provider_lines(dict(summary.get("month_by_provider") or {}))

    return (
        "📊 LLM: tokeny i stoimost\n\n"
        f"Sutki ({summary.get('day_date', 'n/a')}):\n"
        f"- calls={int(day_total.get('calls', 0))}, rows={rows_day}\n"
        f"- tokens={int(day_total.get('total_tokens', 0))} "
        f"(in={int(day_total.get('prompt_tokens', 0))}, out={int(day_total.get('completion_tokens', 0))})\n"
        f"- cost={_fmt_money_usd(float(day_total.get('cost_usd', 0.0)))}\n\n"
        f"Mesyats ({summary.get('month', 'n/a')}):\n"
        f"- calls={int(month_total.get('calls', 0))}, rows={rows_month}\n"
        f"- tokens={int(month_total.get('total_tokens', 0))} "
        f"(in={int(month_total.get('prompt_tokens', 0))}, out={int(month_total.get('completion_tokens', 0))})\n"
        f"- cost={_fmt_money_usd(float(month_total.get('cost_usd', 0.0)))}\n\n"
        "Po provayderam za sutki:\n"
        f"{day_lines}\n\n"
        "Po provayderam za mesyats:\n"
        f"{month_lines}"
    ).strip()


def build_telegram_report_text(now_ts: Optional[float] = None, tz_name: Optional[str] = None) -> str:
    return format_telegram_report(summarize_usage(now_ts=now_ts, tz_name=tz_name))


__all__ = [
    "LEDGER_PATH",
    "PROVIDER_TRACE_PATH",
    "record_safe_chat_call",
    "record_provider_event",
    "summarize_usage",
    "summarize_provider_events",
    "format_telegram_report",
    "build_telegram_report_text",
]
