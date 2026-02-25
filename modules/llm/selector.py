# -*- coding: utf-8 -*-
"""modules/llm/selector.po

Lightweight web chat selector.
The main goal: do not fall into a local stub if the cloud provider is available."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import asyncio
import concurrent.futures
import logging
import os
import time
import urllib.request

from providers.pool import PROVIDERS

from .providers_local import LocalProvider

log = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in ("1", "true", "yes", "on", "y")


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return int(default)
    try:
        return int(float(raw))
    except Exception:
        return int(default)


SMART_PROVIDER_NAME = (os.getenv("LLM_SMART_PROVIDER", "gpt-5-mini") or "gpt-5-mini").strip().lower()
REFLEX_PROVIDER_NAME = (os.getenv("LLM_REFLEX_PROVIDER", "local") or "local").strip().lower()
HIVE_BG_CLOUD_AUTO_BY_LOCAL = _env_bool("HIVE_BG_CLOUD_AUTO_BY_LOCAL", False)
HIVE_BG_CLOUD_PROVIDER = (os.getenv("HIVE_BG_CLOUD_PROVIDER", SMART_PROVIDER_NAME) or SMART_PROVIDER_NAME).strip().lower()
SELECTOR_TOTAL_TIMEOUT_SEC = max(1.0, _env_float("ESTER_CHAT_TOTAL_TIMEOUT_SEC", 18.0))
SELECTOR_PROVIDER_TIMEOUT_SEC = max(0.8, _env_float("ESTER_CHAT_PROVIDER_TIMEOUT_SEC", 7.0))
SELECTOR_REQUEST_TIMEOUT_SEC = max(0.8, _env_float("ESTER_SELECTOR_REQUEST_TIMEOUT_SEC", 7.0))
_CALL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(2, _env_int("ESTER_SELECTOR_WORKERS", 4)),
    thread_name_prefix="ester_selector",
)

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
            channel=str(channel or "unknown"),
            provider=str(provider or "unknown"),
            event=str(event or "event"),
            ok=bool(ok),
            latency_ms=int(latency_ms or 0),
            error=str(error or ""),
            source="modules.llm.selector",
            meta=dict(meta or {}),
        )
    except Exception:
        return


def _canon_provider(name: str) -> str:
    n = str(name or "").strip().lower()
    if n in ("", "auto", "any", "smart", "cloud", "judge"):
        n = SMART_PROVIDER_NAME
    try:
        return PROVIDERS._canon_name(n)  # type: ignore[attr-defined]
    except Exception:
        return n


def _provider_enabled(name: str) -> bool:
    n = _canon_provider(name)
    if not n:
        return False
    try:
        return bool(PROVIDERS.has(n) and PROVIDERS.enabled(n))
    except Exception:
        return False


def _probe_local_runtime_online(timeout_sec: float = 0.8) -> bool:
    try:
        if not _provider_enabled("local"):
            return False
        base_url = str(getattr(PROVIDERS.cfg("local"), "base_url", "") or "").strip().rstrip("/")
        if not base_url:
            return False
        models_url = f"{base_url}/models" if base_url.endswith("/v1") else f"{base_url}/v1/models"
        req = urllib.request.Request(models_url, method="GET")
        with urllib.request.urlopen(req, timeout=max(0.2, float(timeout_sec))) as resp:  # noqa: S310 (local URL from env)
            code = int(getattr(resp, "status", 200) or 200)
        return 200 <= code < 500
    except Exception:
        return False


def _pick_bg_cloud_provider() -> str:
    candidates = [HIVE_BG_CLOUD_PROVIDER, SMART_PROVIDER_NAME, "gpt-5-mini", "gemini", "local"]
    seen = set()
    for item in candidates:
        n = _canon_provider(item)
        if not n or n in seen:
            continue
        seen.add(n)
        if _provider_enabled(n):
            return n
    return "local"


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


class _PoolAdapter:
    def __init__(self, name: str) -> None:
        self.name = _canon_provider(name) or "local"

    async def _request(
        self,
        *,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        request_timeout_sec: Optional[float] = None,
        channel: str = "unknown",
    ) -> str:
        cfg = PROVIDERS.cfg(self.name)
        client = PROVIDERS.client(self.name)

        messages: List[Dict[str, Any]] = []
        if str(system_prompt or "").strip():
            messages.append({"role": "system", "content": str(system_prompt)})
        messages.append({"role": "user", "content": str(prompt or "")})

        kwargs: Dict[str, Any] = {
            "model": cfg.model,
            "messages": messages,
            "temperature": float(temperature),
        }
        if isinstance(max_tokens, int) and max_tokens > 0:
            kwargs["max_tokens"] = int(max_tokens)

        timeout_cap = float(getattr(cfg, "timeout", 0.0) or 0.0)
        try:
            if hasattr(PROVIDERS, "timeout_for_channel"):
                timeout_cap = float(PROVIDERS.timeout_for_channel(self.name, channel=channel) or timeout_cap)  # type: ignore[attr-defined]
        except Exception:
            pass

        try:
            req_timeout = float(request_timeout_sec if request_timeout_sec is not None else SELECTOR_REQUEST_TIMEOUT_SEC)
        except Exception:
            req_timeout = float(SELECTOR_REQUEST_TIMEOUT_SEC)
        if timeout_cap > 0.0:
            req_timeout = max(0.8, min(float(timeout_cap), float(req_timeout)))
        else:
            req_timeout = max(0.8, float(req_timeout))

        try:
            resp = await asyncio.wait_for(client.chat.completions.create(**kwargs), timeout=req_timeout)
        except Exception as e:
            err = str(e).lower()
            if "unsupported parameter: 'temperature'" in err:
                kwargs.pop("temperature", None)
            if "unsupported parameter: 'max_tokens'" in err or "max_completion_tokens" in err:
                if "max_tokens" in kwargs:
                    mt = kwargs.pop("max_tokens")
                    kwargs["max_completion_tokens"] = mt
            resp = await asyncio.wait_for(client.chat.completions.create(**kwargs), timeout=req_timeout)

        txt = ""
        try:
            txt = str(resp.choices[0].message.content or "").strip()
        except Exception:
            txt = ""
        return txt

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 0,
        request_timeout_sec: Optional[float] = None,
        channel: str = "unknown",
        **_: Any,
    ) -> str:
        mt = int(max_tokens) if isinstance(max_tokens, int) else 0
        if mt <= 0:
            mt = 0
        return str(
            _run_coro_sync(
                self._request(
                    prompt=str(prompt or ""),
                    system_prompt=str(system_prompt or ""),
                    temperature=float(temperature),
                    max_tokens=(mt if mt > 0 else None),
                    request_timeout_sec=request_timeout_sec,
                    channel=channel,
                )
            )
            or ""
        ).strip()

    def chat(self, message: str, history: List[Dict[str, Any]] | None = None, **kwargs: Any) -> str:
        return self.generate(
            prompt=message,
            system_prompt=str(kwargs.get("system_prompt") or ""),
            temperature=float(kwargs.get("temperature", 0.7) or 0.7),
            max_tokens=int(kwargs.get("max_tokens", 0) or 0),
            request_timeout_sec=(None if kwargs.get("request_timeout_sec") is None else float(kwargs.get("request_timeout_sec"))),
            channel=str(kwargs.get("channel") or "unknown"),
        )

    def smoketest(self) -> str:
        if self.name == "local":
            return "OK" if _probe_local_runtime_online() else "FAILED: local_runtime_offline"
        return "OK" if _provider_enabled(self.name) else "FAILED: provider_disabled"


def get_adapter_by_name(name: str):
    n = _canon_provider(name)
    if n and _provider_enabled(n):
        return _PoolAdapter(n)
    return LocalProvider()


def route_task(intent: str = "chat") -> Tuple[str, Any]:
    intent = str(intent or "chat").strip().lower()

    if intent in ("sleep", "dream", "background", "reflex", "fast", "ping"):
        if HIVE_BG_CLOUD_AUTO_BY_LOCAL:
            if _probe_local_runtime_online():
                target = REFLEX_PROVIDER_NAME or "local"
            else:
                target = _pick_bg_cloud_provider()
        else:
            target = REFLEX_PROVIDER_NAME or "local"

        if not _provider_enabled(target):
            target = _pick_bg_cloud_provider()
        return (target, get_adapter_by_name(target))

    target = SMART_PROVIDER_NAME or "gpt-5-mini"
    if not _provider_enabled(target):
        target = _pick_bg_cloud_provider()
    return (target, get_adapter_by_name(target))


def _fallback_chain(first: str) -> List[str]:
    candidates = [first, SMART_PROVIDER_NAME, "gpt-5-mini", "gemini", "local"]
    out: List[str] = []
    seen = set()
    for item in candidates:
        n = _canon_provider(item)
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def chat(
    message: str,
    history: List[Dict[str, Any]] | None = None,
    intent: str = "chat",
    **kwargs: Any,
) -> Dict[str, Any]:
    forced = kwargs.get("mode") or kwargs.get("provider")
    if forced:
        selected = _canon_provider(str(forced))
    else:
        selected, _ = route_task(intent)
    selected = _canon_provider(selected)

    system_prompt = str(kwargs.get("system_prompt") or "")
    temperature = float(kwargs.get("temperature", 0.7) or 0.7)
    max_tokens = int(kwargs.get("max_tokens", 0) or 0)
    channel = str(kwargs.get("channel") or kwargs.get("source_channel") or "unknown").strip().lower() or "unknown"
    total_budget_sec = max(1.0, float(kwargs.get("total_timeout_sec") or SELECTOR_TOTAL_TIMEOUT_SEC))
    per_provider_timeout_sec = max(0.8, float(kwargs.get("provider_timeout_sec") or SELECTOR_PROVIDER_TIMEOUT_SEC))
    deadline = time.monotonic() + total_budget_sec
    attempts: List[Dict[str, Any]] = []

    last_error = None
    for name in _fallback_chain(selected):
        remain = deadline - time.monotonic()
        if remain <= 0.0:
            attempts.append({"provider": name, "event": "budget_exhausted", "ok": False, "latency_ms": 0})
            _record_provider_event(
                channel=channel,
                provider=name,
                event="budget_exhausted",
                ok=False,
                error="budget_exhausted",
            )
            break

        timeout_this = max(0.8, min(per_provider_timeout_sec, remain))
        prov = get_adapter_by_name(name)
        _record_provider_event(channel=channel, provider=name, event="attempt", ok=True)
        t0 = time.monotonic()
        try:
            if hasattr(prov, "generate"):
                fut = _CALL_EXECUTOR.submit(
                    prov.generate,
                    str(message or ""),
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    request_timeout_sec=timeout_this,
                    channel=channel,
                )
                out = fut.result(timeout=timeout_this)
            elif hasattr(prov, "chat"):
                chat_kwargs = dict(kwargs or {})
                chat_kwargs.setdefault("request_timeout_sec", timeout_this)
                chat_kwargs.setdefault("channel", channel)
                fut = _CALL_EXECUTOR.submit(
                    prov.chat,
                    str(message or ""),
                    history=history,
                    **chat_kwargs,
                )
                out = fut.result(timeout=timeout_this)
            else:
                continue
            out = str(out or "").strip()
            dt_ms = int(max(0.0, (time.monotonic() - t0) * 1000.0))
            if out:
                attempts.append({"provider": name, "event": "success", "ok": True, "latency_ms": dt_ms})
                _record_provider_event(
                    channel=channel,
                    provider=name,
                    event="success",
                    ok=True,
                    latency_ms=dt_ms,
                )
                return {"ok": True, "provider": name, "answer": out, "provider_attempts": attempts}
            attempts.append({"provider": name, "event": "empty", "ok": False, "latency_ms": dt_ms})
            _record_provider_event(
                channel=channel,
                provider=name,
                event="empty",
                ok=False,
                latency_ms=dt_ms,
                error="empty_reply",
            )
        except concurrent.futures.TimeoutError:
            dt_ms = int(max(0.0, (time.monotonic() - t0) * 1000.0))
            attempts.append({"provider": name, "event": "timeout", "ok": False, "latency_ms": dt_ms})
            _record_provider_event(
                channel=channel,
                provider=name,
                event="timeout",
                ok=False,
                latency_ms=dt_ms,
                error="selector_timeout",
            )
        except Exception as e:
            last_error = e
            dt_ms = int(max(0.0, (time.monotonic() - t0) * 1000.0))
            attempts.append(
                {
                    "provider": name,
                    "event": "failure",
                    "ok": False,
                    "latency_ms": dt_ms,
                    "error": str(e),
                }
            )
            _record_provider_event(
                channel=channel,
                provider=name,
                event="failure",
                ok=False,
                latency_ms=dt_ms,
                error=str(e),
            )
            try:
                log.warning("[selector] provider=%s failed: %s", name, e)
            except Exception:
                pass

    local_fallback = LocalProvider()
    fb_t0 = time.monotonic()
    answer = local_fallback.chat(message=message, history=history, **kwargs)
    fb_ms = int(max(0.0, (time.monotonic() - fb_t0) * 1000.0))
    attempts.append({"provider": "local_stub", "event": "fallback_success", "ok": True, "latency_ms": fb_ms})
    _record_provider_event(
        channel=channel,
        provider="local_stub",
        event="fallback_success",
        ok=True,
        latency_ms=fb_ms,
    )
    payload: Dict[str, Any] = {"ok": True, "provider": "local_stub", "answer": answer, "provider_attempts": attempts}
    if last_error is not None:
        payload["error"] = str(last_error)
    return payload


def health() -> Dict[str, Any]:
    local_state = "OK" if _probe_local_runtime_online() else "FAILED: local_runtime_offline"
    smart_name = _canon_provider(SMART_PROVIDER_NAME)
    smart_state = "OK" if _provider_enabled(smart_name) else "FAILED: provider_disabled"
    return {
        "ok": ("OK" in local_state) or ("OK" in smart_state),
        "local": local_state,
        "smart": smart_state,
        "active_smart": smart_name,
    }
