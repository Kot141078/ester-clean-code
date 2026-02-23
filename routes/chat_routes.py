# -*- coding: utf-8 -*-
"""routes/chat_routes.py — CANONICAL chat entrypoint (/chat/*).

Goal:
- One canonical route: POST /chat/message
- One auth contract: JWT OPTIONAL by default (docs/UI expect that)
- Backward compatible payload keys:
    {message|text|query, sid|session_id, mode|engine, rag|use_rag, temperature}
- Backward compatible response keys:
    {ok, answer, response, reply, provider, mode, sid}

Legacy note:
- routes_chat.py should run under /chat-legacy/* unless explicitly enabled.

Earth paragraph:
Single inlet valve — one nozzle, one pressure rule. Two different auth-rules
for the same path give backflow (hard-to-debug failures).
"""

from __future__ import annotations

import os
import sys
import zlib
import asyncio
import importlib
import logging
import time
import traceback
import concurrent.futures
from typing import Dict, Any, Optional, Tuple, List

from flask import Blueprint, request, jsonify


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
        return bool(default)
    return v in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    v = (os.getenv(name) or "").strip()
    if not v:
        return float(default)
    try:
        return float(v)
    except Exception:
        return float(default)


def _env_int(name: str, default: int) -> int:
    v = (os.getenv(name) or "").strip()
    if not v:
        return int(default)
    try:
        return int(float(v))
    except Exception:
        return int(default)


def _maybe_verify_jwt() -> Tuple[bool, Optional[str]]:
    """JWT contract for /chat/message.

    Default: OPTIONAL.
    If ESTER_CHAT_REQUIRE_JWT=1 -> REQUIRED.

    Returns: (ok, error_code)
    """
    # Default is optional JWT; explicit env flag can force required mode.
    require = _env_bool("ESTER_CHAT_REQUIRE_JWT", False)

    try:
        from flask_jwt_extended import verify_jwt_in_request  # type: ignore
        verify_jwt_in_request(optional=not require)
        return True, None
    except Exception as e:
        if not require:
            return True, None
        return False, f"jwt_required:{type(e).__name__}"


def _pick_message(data: Dict[str, Any]) -> str:
    return (data.get("message") or data.get("text") or data.get("query") or "").strip()


def _pick_sid(data: Dict[str, Any]) -> str:
    sid = (data.get("sid") or data.get("session_id") or data.get("session") or data.get("chat_id") or "").strip()
    if not sid:
        sid = (os.getenv("ESTER_CHAT_SID_DEFAULT") or os.getenv("ESTER_FORCE_SID") or "default").strip() or "default"
    return sid


def _pick_mode(data: Dict[str, Any]) -> str:
    mode = (data.get("mode") or data.get("engine") or data.get("provider") or "").strip()
    if not mode:
        mode = (os.getenv("ESTER_DEFAULT_MODE") or os.getenv("ESTER_CHAT_MODE") or "local").strip() or "local"
    return mode


def _pick_rag(data: Dict[str, Any]) -> bool:
    if "use_rag" in data:
        return bool(data.get("use_rag"))
    if "rag" in data:
        return bool(data.get("rag"))
    return _env_bool("ESTER_DEFAULT_RAG", _env_bool("ESTER_RAG_ENABLE", False))


def _pick_temp(data: Dict[str, Any]) -> float:
    if "temperature" not in data:
        return _env_float("ESTER_DEFAULT_TEMP", 0.7)
    try:
        return float(data.get("temperature"))
    except Exception:
        return _env_float("ESTER_DEFAULT_TEMP", 0.7)


def _stable_chat_id(raw_sid: str) -> int:
    sid = str(raw_sid or "web-ui").strip() or "web-ui"
    if sid.lstrip("-").isdigit():
        try:
            return int(sid)
        except Exception:
            pass
    return int(900000000 + (zlib.adler32(sid.encode("utf-8")) % 100000000))


def _run_coro_sync(coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            try:
                loop.close()
            except Exception:
                pass


def _call_main_live_arbitrage(
    *,
    text: str,
    sid: str,
    user_id: str,
    user_name: str,
    address_as: str,
    tone_context: str = "",
    file_context: str = "",
) -> str:
    main_mod = sys.modules.get("__main__")
    run_mod = sys.modules.get("run_ester_fixed")
    if run_mod is None:
        try:
            run_mod = importlib.import_module("run_ester_fixed")
        except Exception:
            run_mod = None

    arb = None
    run_sync = None
    for mod in (main_mod, run_mod):
        if mod is None:
            continue
        fn = getattr(mod, "ester_arbitrage", None)
        if callable(fn):
            arb = fn
            run_sync = getattr(mod, "_run_coro_sync", None)
            break

    if not callable(arb):
        return ""


_ARB_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(1, _env_int("ESTER_WEB_ARBITRAGE_WORKERS", 2)),
    thread_name_prefix="ester_web_arb",
)


def _call_main_live_arbitrage_with_timeout(
    *,
    timeout_sec: float,
    text: str,
    sid: str,
    user_id: str,
    user_name: str,
    address_as: str,
    tone_context: str = "",
    file_context: str = "",
) -> Tuple[str, str]:
    fut = _ARB_EXECUTOR.submit(
        _call_main_live_arbitrage,
        text=text,
        sid=sid,
        user_id=user_id,
        user_name=user_name,
        address_as=address_as,
        tone_context=tone_context,
        file_context=file_context,
    )
    try:
        out = str(fut.result(timeout=max(0.1, float(timeout_sec))) or "").strip()
        if out:
            return out, "success"
        return "", "empty"
    except concurrent.futures.TimeoutError:
        try:
            fut.cancel()
        except Exception:
            pass
        return "", "timeout"
    except Exception:
        return "", "error"
    chat_id = _stable_chat_id(sid)
    try:
        kwargs = {
            "user_text": str(text or ""),
            "user_id": str(user_id or sid or "web"),
            "user_name": str(user_name or "WebUser"),
            "chat_id": int(chat_id),
            "address_as": str(address_as or user_name or "Polzovatel"),
            "tone_context": str(tone_context or ""),
            "file_context": str(file_context or ""),
            "channel": "web",
        }
        try:
            coro = arb(**kwargs)
        except TypeError:
            kwargs.pop("channel", None)
            coro = arb(**kwargs)
        out = run_sync(coro) if callable(run_sync) else _run_coro_sync(coro)
        return str(out or "").strip()
    except Exception as e:
        try:
            logging.warning("[chat_routes] live arbitrage failed: %s", e)
        except Exception:
            pass
        return ""


def _answer_text_and_meta(answer: Any) -> Tuple[str, Dict[str, Any]]:
    if isinstance(answer, dict):
        text = str(
            answer.get("answer")
            or answer.get("response")
            or answer.get("reply")
            or answer.get("text")
            or ""
        ).strip()
        return text, answer
    return str(answer or "").strip(), {}


try:
    from modules.proactivity import token_cost_report as _token_cost_report
except Exception:  # pragma: no cover
    _token_cost_report = None  # type: ignore


def _record_provider_event(
    *,
    channel: str,
    provider: str,
    event: str,
    ok: bool,
    latency_ms: int = 0,
    error: str = "",
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        if _token_cost_report is None:
            return
        _token_cost_report.record_provider_event(
            channel=str(channel or "web"),
            provider=str(provider or "unknown"),
            event=str(event or "event"),
            ok=bool(ok),
            latency_ms=int(latency_ms or 0),
            error=str(error or ""),
            source="routes.chat_routes",
            meta=dict(meta or {}),
        )
    except Exception:
        return


def _emotions_from_text(text: str, answer_text: str) -> Dict[str, float]:
    src = f"{text} {answer_text}".lower()
    emo = {
        "joy": 0.0,
        "sadness": 0.0,
        "anger": 0.0,
        "fear": 0.0,
        "interest": 0.0,
    }
    lex = {
        "joy": ("rad", "schast", "klass", "luchshiy", "otlich"),
        "sadness": ("grust", "pechal", "tosk", "plokho"),
        "anger": ("zl", "yarost", "besit", "nenavizh"),
        "fear": ("strakh", "boyu", "trevog", "voln"),
        "interest": ("kak", "pochemu", "chto", "zachem", "?"),
    }
    for key, words in lex.items():
        score = 0.0
        for w in words:
            if w in src:
                score += 0.25
        emo[key] = min(1.0, score)
    if all(v <= 0.0 for v in emo.values()):
        emo["interest"] = 0.1
    return emo
_ab = (os.environ.get("ESTER_CHAT_AB") or "A").upper()
bp = Blueprint(f"chat_{_ab}", __name__, url_prefix="/chat")

from modules.util import history as hist
from modules.llm.selector import chat as llm_chat, health as llm_health
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@bp.get("/health")
def health() -> Any:
    return jsonify({"ok": True, "llm": llm_health()})


@bp.get("/history")
def history() -> Any:
    sid = (request.args.get("sid") or os.getenv("ESTER_CHAT_SID_DEFAULT") or "default").strip() or "default"
    try:
        limit = int(request.args.get("limit") or 50)
    except Exception:
        limit = 50
    items = hist.load(sid)[-max(0, min(limit, 500)):]
    return jsonify({"ok": True, "sid": sid, "history": items})


@bp.post("/message")
def message() -> Any:
    t0 = time.monotonic()
    ok, err = _maybe_verify_jwt()
    if not ok:
        return jsonify({"ok": False, "error": err or "jwt_required"}), 401

    data = request.get_json(silent=True) or {}
    text = _pick_message(data)
    if not text:
        return jsonify({"ok": False, "error": "empty_message"}), 400

    sid = _pick_sid(data)
    mode = _pick_mode(data)
    use_rag = _pick_rag(data)
    temperature = _pick_temp(data)
    channel = "web"
    provider_trace: List[Dict[str, Any]] = []

    answer: Any
    live_enabled = _env_bool("ESTER_WEB_USE_ARBITRAGE", True)
    live_text = ""
    live_status = "disabled"
    if live_enabled:
        live_timeout_sec = _env_float("ESTER_WEB_ARBITRAGE_TIMEOUT_SEC", 6.0)
        live_attempt_t0 = time.monotonic()
        _record_provider_event(channel=channel, provider="hivemind", event="attempt", ok=True)
        live_text, live_status = _call_main_live_arbitrage_with_timeout(
            timeout_sec=live_timeout_sec,
            text=text,
            sid=sid,
            user_id=str(data.get("user_id") or data.get("uid") or sid or "web"),
            user_name=str(data.get("user_name") or data.get("user") or "WebUser"),
            address_as=str(data.get("address_as") or data.get("user_name") or data.get("user") or "Polzovatel"),
            tone_context=str(data.get("tone_context") or ""),
            file_context=str(data.get("file_context") or ""),
        )
        live_ms = int(max(0.0, (time.monotonic() - live_attempt_t0) * 1000.0))
        if live_text:
            _record_provider_event(channel=channel, provider="hivemind", event="success", ok=True, latency_ms=live_ms)
        else:
            _record_provider_event(
                channel=channel,
                provider="hivemind",
                event=live_status if live_status in {"timeout", "error"} else "fallback",
                ok=False,
                latency_ms=live_ms,
                error=live_status,
            )
        provider_trace.append(
            {
                "provider": "hivemind",
                "event": "success" if live_text else live_status,
                "latency_ms": live_ms,
            }
        )

    if live_text:
        answer = {"ok": True, "provider": "hivemind", "answer": live_text}
    else:
        history_items = hist.load(sid)
        try:
            answer = llm_chat(
                message=text,
                history=history_items,
                mode=mode,
                sid=sid,
                use_rag=use_rag,
                temperature=temperature,
                channel=channel,
            )
        except TypeError:
            answer = llm_chat(text, history_items, mode)
        except Exception:
            traceback.print_exc()
            return jsonify({"ok": False, "error": "chat_failed"}), 500

    try:
        hist.append(sid, "user", text)
        hist.append(sid, "assistant", answer)
    except Exception:
        pass

    answer_text, answer_meta = _answer_text_and_meta(answer)
    emotions = _emotions_from_text(text, answer_text)
    proactive: Dict[str, Any] = {"hints": []}
    if "?" in text:
        proactive["hints"].append("clarify_goal")

    sources = answer_meta.get("sources")
    if not isinstance(sources, list):
        sources = []
    if not sources:
        sources = [{"id": "chat-local", "score": 0.0}]

    provider_name = str(answer_meta.get("provider") or mode)
    selector_trace = answer_meta.get("provider_attempts")
    if isinstance(selector_trace, list) and selector_trace:
        for row in selector_trace:
            if isinstance(row, dict):
                provider_trace.append(dict(row))
    local_providers = answer_meta.get("providers_local")
    if not isinstance(local_providers, list) or not local_providers:
        local_providers = ["local"]

    memory_hits = answer_meta.get("memory_hits")
    if not isinstance(memory_hits, list):
        memory_hits = []

    filters = answer_meta.get("filters")
    if not isinstance(filters, (dict, list)):
        filters = {}

    judge_name = data.get("judge") or answer_meta.get("judge")
    if not judge_name and mode in ("cloud", "judge"):
        judge_name = "openai"

    elapsed_ms = int(max(0.0, (time.monotonic() - t0) * 1000.0))
    _record_provider_event(
        channel=channel,
        provider=provider_name,
        event="response",
        ok=bool(answer_text),
        latency_ms=elapsed_ms,
        meta={"mode": mode, "live_status": live_status},
    )

    return jsonify({
        "ok": True,
        "sid": sid,
        "mode": mode,
        "provider": provider_name,
        "rag": use_rag,
        "temperature": temperature,
        "answer": answer_text,
        "response": answer_text,
        "reply": answer_text,
        "answer_raw": answer_meta or answer,
        "emotions": emotions,
        "proactive": proactive,
        "sources": sources,
        "providers_local": local_providers,
        "memory_hits": memory_hits,
        "filters": filters,
        "judge": judge_name,
        "provider_trace": provider_trace,
        "latency_ms": elapsed_ms,
    })


def register(app) -> None:
    """Idempotent registration helper."""
    try:
        if getattr(app, "blueprints", None) and bp.name in app.blueprints:
            return
        app.register_blueprint(bp)
    except Exception:
        pass
