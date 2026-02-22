# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, Optional

from modules.runtime import oracle_requests, oracle_window
from modules.security.provider_keys import get_provider_key

_FIXED_URL = "https://api.openai.com/v1/chat/completions"
_FIXED_HOST = "api.openai.com"


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _network_enabled_env() -> bool:
    return _truthy(os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")) or _truthy(os.getenv("ESTER_ALLOW_NETWORK", "0"))


def _slot() -> str:
    raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def _dry_run_default() -> bool:
    return not _truthy(os.getenv("ESTER_ORACLE_DRY_RUN_DISABLE", "0"))


def reset_slot_b_fallback() -> Dict[str, Any]:
    # Backward-compatible no-op in Iter38.
    return {"ok": True, "slot_b_disabled": False}


def _resolve_model(value: str) -> str:
    model = str(value or "").strip()
    if model:
        return model
    model = str(os.getenv("ESTER_ORACLE_MODEL", "") or "").strip()
    if model:
        return model
    return ""


def _resolve_api_key() -> str:
    key = str(get_provider_key("OPENAI_API_KEY") or "").strip()
    if key:
        return key
    key = str(os.getenv("ESTER_OPENAI_API_KEY", "") or "").strip()
    return key


def _bounded_temperature(value: Any) -> float:
    try:
        f = float(value)
    except Exception:
        f = 0.2
    if f < 0.0:
        f = 0.0
    if f > 2.0:
        f = 2.0
    return float(f)


def _bounded_max_tokens(value: Any) -> int:
    try:
        n = int(value)
    except Exception:
        n = 256
    if n < 1:
        n = 1
    if n > 4096:
        n = 4096
    return int(n)


def _deny_and_note(
    *,
    window_id: str,
    call_id: str,
    request_id: str,
    actor: str,
    agent_id: str,
    plan_id: str,
    step_index: Optional[int],
    model: str,
    prompt_digest: str,
    input_chars: int,
    est_tokens_in: int,
    max_tokens: int,
    error: str,
    policy_hit: str,
) -> Dict[str, Any]:
    row = {
        "window_id": str(window_id or ""),
        "call_id": str(call_id or ""),
        "request_id": str(request_id or ""),
        "actor": str(actor or "ester"),
        "agent_id": str(agent_id or ""),
        "plan_id": str(plan_id or ""),
        "step_index": step_index,
        "model": str(model or ""),
        "prompt_digest": str(prompt_digest or ""),
        "input_chars": int(input_chars),
        "est_tokens_in": int(est_tokens_in),
        "max_tokens": int(max_tokens),
        "ok": False,
        "latency_ms": 0,
        "tokens_out": 0,
        "error": str(error or ""),
        "policy_hit": str(policy_hit or ""),
    }
    oracle_window.note_call(str(window_id or ""), row)
    return {
        "ok": False,
        "error": str(error or ""),
        "policy_hit": str(policy_hit or ""),
        "window_id": str(window_id or ""),
        "call_id": str(call_id or ""),
        "request_id": str(request_id or ""),
        "network_attempted": False,
    }


def call(
    prompt: str,
    model: str = "gpt-4o-mini",
    timeout: int = 20,
    *,
    window_id: str = "",
    reason: str = "",
    dry_run: Optional[bool] = None,
    budgets: Optional[Dict[str, Any]] = None,  # kept for compatibility
    gate: Any = None,  # kept for compatibility
    max_tokens: int = 256,
    temperature: float = 0.2,
    purpose: str = "",
    actor: str = "ester",
    agent_id: str = "",
    plan_id: str = "",
    step_index: Optional[int] = None,
    request_id: str = "",
) -> Dict[str, Any]:
    del budgets, gate
    prompt_text = str(prompt or "")
    clean_model = _resolve_model(str(model or ""))
    model_for_call = clean_model or "gpt-4o-mini"
    call_purpose = str(purpose or reason or "").strip() or "oracle_call"
    requested_tokens = _bounded_max_tokens(max_tokens)
    temp = _bounded_temperature(temperature)
    requested_wall_ms = max(100, int(timeout or 20) * 1000)
    actor_clean = str(actor or "ester")
    req_id = str(request_id or "").strip()
    input_chars = len(prompt_text)
    est_tokens_in = max(1, (input_chars + 3) // 4)
    prompt_digest = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

    def _deny(error: str, policy_hit: str, *, window: str = "") -> Dict[str, Any]:
        return _deny_and_note(
            window_id=str(window or ""),
            call_id="oc_" + uuid.uuid4().hex[:12],
            request_id=req_id,
            actor=actor_clean,
            agent_id=str(agent_id or ""),
            plan_id=str(plan_id or ""),
            step_index=step_index,
            model=model_for_call,
            prompt_digest=prompt_digest,
            input_chars=input_chars,
            est_tokens_in=est_tokens_in,
            max_tokens=requested_tokens,
            error=error,
            policy_hit=policy_hit,
        )

    current = oracle_window.current_window()
    if not bool(current.get("open")):
        return _deny("oracle_window_closed", "oracle_window_closed")
    active_window = str(current.get("window_id") or "")

    if str(window_id or "").strip() and str(window_id).strip() != active_window:
        return _deny("oracle_window_mismatch", "oracle_window_mismatch", window=active_window)

    if _slot() != "B":
        return _deny("oracle_slot_closed", "slot_a", window=active_window)

    if not clean_model:
        return _deny("model_required", "oracle_model_required", window=active_window)

    if str(agent_id or "").strip():
        if not req_id:
            return _deny("oracle_not_approved", "request_id_required", window=active_window)
        win_actor = str(current.get("actor") or "").strip().lower()
        if not (win_actor == "ester" or win_actor.startswith("ester:")):
            return _deny("actor_not_ester", "window_actor_not_ester", window=active_window)
        if not bool(current.get("allow_agents")):
            return _deny("oracle_not_approved", "window_allow_agents_false", window=active_window)
        req_check = oracle_requests.validate_approved_request(
            request_id=req_id,
            agent_id=str(agent_id or ""),
            plan_id=str(plan_id or ""),
            step_index=step_index,
            model=model_for_call,
            window_id=active_window,
        )
        if not bool(req_check.get("ok")):
            return _deny(
                str(req_check.get("error") or "request_mismatch"),
                str(req_check.get("policy_hit") or "request_mismatch"),
                window=active_window,
            )
        approved_ids = [str(x) for x in list(((current.get("meta") or {}).get("approved_request_ids") or []))]
        if approved_ids and req_id not in approved_ids:
            return _deny("request_mismatch", "window_request_binding", window=active_window)

    auth = oracle_window.authorize_call(
        window_id=active_window,
        actor=actor_clean,
        agent_id=str(agent_id or ""),
        plan_id=str(plan_id or ""),
        step_index=step_index,
        model=clean_model,
        prompt=prompt_text,
        max_tokens=requested_tokens,
        purpose=call_purpose,
        requested_wall_ms=requested_wall_ms,
    )
    call_id = str(auth.get("call_id") or "")
    if not bool(auth.get("ok")):
        err = str(auth.get("error") or "oracle_denied")
        if err == "oracle_budget_exceeded":
            err = "budgets_exhausted"
        return {
            "ok": False,
            "error": err,
            "policy_hit": str(auth.get("policy_hit") or ""),
            "window_id": str(auth.get("window_id") or active_window),
            "call_id": call_id,
            "request_id": req_id,
            "network_attempted": False,
        }

    prompt_digest = str(auth.get("prompt_digest") or prompt_digest)
    est_tokens_in = int(auth.get("est_tokens_in") or est_tokens_in)
    input_chars = int(auth.get("input_chars") or input_chars)
    active_window = str(auth.get("window_id") or active_window)

    use_dry = _dry_run_default() if dry_run is None else bool(dry_run)
    if use_dry:
        row = {
            "window_id": active_window,
            "call_id": call_id,
            "request_id": req_id,
            "actor": actor_clean,
            "agent_id": str(agent_id or ""),
            "plan_id": str(plan_id or ""),
            "step_index": step_index,
            "model": model_for_call,
            "prompt_digest": prompt_digest,
            "input_chars": input_chars,
            "est_tokens_in": est_tokens_in,
            "max_tokens": requested_tokens,
            "ok": True,
            "latency_ms": 0,
            "tokens_out": 0,
            "error": "",
            "dry_run": True,
            "policy_hit": "oracle_window",
        }
        oracle_window.note_call(active_window, row)
        return {
            "ok": True,
            "dry_run": True,
            "provider": "openai_oracle",
            "model": model_for_call,
            "text": "oracle_dry_run",
            "window_id": active_window,
            "call_id": call_id,
            "request_id": req_id,
            "usage": {"prompt_tokens": est_tokens_in, "completion_tokens": 0, "total_tokens": est_tokens_in},
            "network_attempted": False,
        }

    if not _network_enabled_env():
        return _deny_and_note(
            window_id=active_window,
            call_id=call_id,
            request_id=req_id,
            actor=actor_clean,
            agent_id=str(agent_id or ""),
            plan_id=str(plan_id or ""),
            step_index=step_index,
            model=model_for_call,
            prompt_digest=prompt_digest,
            input_chars=input_chars,
            est_tokens_in=est_tokens_in,
            max_tokens=requested_tokens,
            error="outbound_network_disabled",
            policy_hit="oracle_network_disabled",
        )

    api_key = _resolve_api_key()
    if not api_key:
        return _deny_and_note(
            window_id=active_window,
            call_id=call_id,
            request_id=req_id,
            actor=actor_clean,
            agent_id=str(agent_id or ""),
            plan_id=str(plan_id or ""),
            step_index=step_index,
            model=model_for_call,
            prompt_digest=prompt_digest,
            input_chars=input_chars,
            est_tokens_in=est_tokens_in,
            max_tokens=requested_tokens,
            error="openai_api_key_missing",
            policy_hit="oracle_api_key_missing",
        )

    parsed = urllib.parse.urlparse(_FIXED_URL)
    if parsed.hostname != _FIXED_HOST:
        return {
            "ok": False,
            "error": "fixed_host_mismatch",
            "window_id": active_window,
            "call_id": call_id,
            "request_id": req_id,
            "network_attempted": False,
        }

    payload = {
        "model": model_for_call,
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": requested_tokens,
        "temperature": temp,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(_FIXED_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + api_key)

    started = time.monotonic()
    timeout_sec = max(1, min(int(timeout or 20), int(auth.get("max_wall_ms_per_call") or 20000) // 1000))
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # nosec B310
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        choice = (((data or {}).get("choices") or [{}])[0].get("message") or {})
        text = str(choice.get("content") or "")
        usage = dict((data or {}).get("usage") or {})
        prompt_tokens = int(usage.get("prompt_tokens") or est_tokens_in)
        completion_tokens = int(usage.get("completion_tokens") or max(0, len(text) // 4))
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        latency_ms = max(0, int((time.monotonic() - started) * 1000))
        row = {
            "window_id": active_window,
            "call_id": call_id,
            "request_id": req_id,
            "actor": actor_clean,
            "agent_id": str(agent_id or ""),
            "plan_id": str(plan_id or ""),
            "step_index": step_index,
            "model": model_for_call,
            "prompt_digest": prompt_digest,
            "input_chars": input_chars,
            "est_tokens_in": est_tokens_in,
            "max_tokens": requested_tokens,
            "ok": True,
            "latency_ms": latency_ms,
            "tokens_out": completion_tokens,
            "error": "",
            "policy_hit": "oracle_window",
        }
        if _truthy(os.getenv("ESTER_ORACLE_LOG_PROMPTS", "0")):
            row["prompt_plaintext"] = prompt_text
        oracle_window.note_call(active_window, row)
        return {
            "ok": True,
            "provider": "openai_oracle",
            "model": model_for_call,
            "text": text,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "window_id": active_window,
            "call_id": call_id,
            "request_id": req_id,
            "network_attempted": True,
        }
    except urllib.error.HTTPError as exc:
        latency_ms = max(0, int((time.monotonic() - started) * 1000))
        row = {
            "window_id": active_window,
            "call_id": call_id,
            "request_id": req_id,
            "actor": actor_clean,
            "agent_id": str(agent_id or ""),
            "plan_id": str(plan_id or ""),
            "step_index": step_index,
            "model": model_for_call,
            "prompt_digest": prompt_digest,
            "input_chars": input_chars,
            "est_tokens_in": est_tokens_in,
            "max_tokens": requested_tokens,
            "ok": False,
            "latency_ms": latency_ms,
            "tokens_out": 0,
            "error": f"oracle_http_error:{int(exc.code)}",
            "policy_hit": "oracle_provider_http_error",
        }
        oracle_window.note_call(active_window, row)
        return {
            "ok": False,
            "error": "oracle_http_error",
            "status": int(exc.code),
            "window_id": active_window,
            "call_id": call_id,
            "request_id": req_id,
            "network_attempted": True,
        }
    except Exception as exc:
        latency_ms = max(0, int((time.monotonic() - started) * 1000))
        row = {
            "window_id": active_window,
            "call_id": call_id,
            "request_id": req_id,
            "actor": actor_clean,
            "agent_id": str(agent_id or ""),
            "plan_id": str(plan_id or ""),
            "step_index": step_index,
            "model": model_for_call,
            "prompt_digest": prompt_digest,
            "input_chars": input_chars,
            "est_tokens_in": est_tokens_in,
            "max_tokens": requested_tokens,
            "ok": False,
            "latency_ms": latency_ms,
            "tokens_out": 0,
            "error": f"oracle_call_exception:{exc.__class__.__name__}",
            "policy_hit": "oracle_provider_exception",
        }
        oracle_window.note_call(active_window, row)
        return {
            "ok": False,
            "error": "oracle_call_exception",
            "detail": f"{exc.__class__.__name__}: {exc}",
            "window_id": active_window,
            "call_id": call_id,
            "request_id": req_id,
            "network_attempted": True,
        }


__all__ = ["call", "reset_slot_b_fallback"]
