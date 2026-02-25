"""Ester thinking manifest: sborka i opisanie statusa myslitelnykh moduley.

This modul ne delaet setevykh vyzovov i ne zavisit ot Flask.
On mozhet ispolzovatsya:
- kak CLI/skript (cherez scripts.ester_thinking_check/ester_thinking_mode),
- HTTP-routami (/ester/thinking/manifest, /ester/thinking/check),
- vnutrennimi proverkami kachestva.

Vazhno: ne trogaem suschestvuyuschie yadro-moduli i ikh API."""
from __future__ import annotations

from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def get_status() -> Dict[str, Any]:
    """A quick snapshot of key environment flags.

    No side effects: only reading os.environ."""
    import os

    volition = {
        "ESTER_VOLITION_MODE": os.getenv("ESTER_VOLITION_MODE", "A"),
        "ESTER_WILL_PRIORITY_AB": os.getenv("ESTER_WILL_PRIORITY_AB", "A"),
        "ESTER_WILL_SCHED_AB": os.getenv("ESTER_WILL_SCHED_AB", "A"),
    }

    cascade = {
        "ESTER_CASCADE_CTX_AB": os.getenv("ESTER_CASCADE_CTX_AB", "A"),
        "ESTER_CASCADE_GUARD_AB": os.getenv("ESTER_CASCADE_GUARD_AB", "A"),
    }

    trace = {
        "ESTER_TRACE_AB": os.getenv("ESTER_TRACE_AB", "A"),
        "ESTER_THINK_DEBUG_AB": os.getenv("ESTER_THINK_DEBUG_AB", "A"),
    }

    background = {
        "ESTER_BG_DISABLE": os.getenv("ESTER_BG_DISABLE", "0"),
        "THINK_HEARTBEAT_SEC": os.getenv("THINK_HEARTBEAT_SEC"),
    }

    return {
        "volition": volition,
        "cascade": cascade,
        "trace": trace,
        "background": background,
    }


def _probe_module(path: str) -> bool:
    """Checking whether the module can be imported.

    No side effects other than trying to import.
    Used to evaluate sovereignty."""
    import importlib

    try:
        importlib.import_module(path)
        return True
    except Exception:
        return False


def build_manifest() -> Dict[str, Any]:
    """Formiruet polnyy manifest po tekuschey ustanovke.

    Structure:
    {
      "ok": bool,
      "status": {...}, # get_status()
      "modules": {...}, # nalichie klyuchevykh moduley
      "coverage": float, # 0.0 .. 1.0
    }"""
    status = get_status()

    modules = {
        "cascade_closed": _probe_module("modules.thinking.cascade_closed"),
        "cascade_multi_ctx": _probe_module("modules.thinking.cascade_multi_context_adapter"),
        "volition_registry": _probe_module("modules.thinking.volition_registry"),
        "volition_priority": _probe_module("modules.thinking.volition_priority_adapter"),
        "will_scheduler": _probe_module("modules.thinking.will_scheduler_adapter"),
        "always_thinker": _probe_module("modules.always_thinker"),
        "trace_adapter": _probe_module("modules.thinking.thought_trace_adapter"),
        "thinkd": _probe_module("scripts.thinkd_run"),
        "ester_thinking_http": _probe_module("routes.ester_thinking_routes_alias"),
        "ester_thinking_quality_http": _probe_module("routes.ester_thinking_quality_routes_alias"),
        "ester_thinking_manifest_http": _probe_module("routes.ester_thinking_manifest_routes_alias"),
    }

    total = len(modules)
    ready = sum(1 for v in modules.values() if v)
    coverage = float(ready) / float(total) if total else 0.0

    ok = ready > 0

    return {
        "ok": ok,
        "status": status,
        "modules": modules,
        "coverage": coverage,
    }


def human_report(manifest: Dict[str, Any]) -> str:
    """A human-readable summary of the manifesto."""
    status = manifest.get("status", {})
    vol = status.get("volition", {})
    trace = status.get("trace", {})
    bg = status.get("background", {})

    parts = []

    # Volya
    if vol.get("ESTER_VOLITION_MODE") == "B":
        parts.append("will in active human mode")
    else:
        parts.append("will in passive mode (ESTER_VOLITION_MODE != B)")

    # Treys
    if trace.get("ESTER_TRACE_AB") == "B":
        parts.append("deep thinking trace enabled")
    else:
        parts.append("short thinking trace is available with an adapter")

    # Fon
    if bg.get("ESTER_BG_DISABLE") == "0":
        hb = bg.get("THINK_HEARTBEAT_SEC") or "?"  # maybe None
        parts.append(f"background thought cycles of permissions (interval ZZF0Z sec)")
    else:
        parts.append("background thought loops are disabled")

    # Sborka stroki
    return "; ".join(parts)


def get_manifest() -> Dict[str, Any]:
    """Publichnyy helper dlya HTTP-routov i skriptov.

    Vozvraschaet polnyy manifest v tom zhe formate, chto build_manifest().
    Vydelen otdelno, chtoby ne lomat suschestvuyuschie importy."""
    return build_manifest()


def describe_manifest(manifest: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Kompaktnoe predstavlenie manifest dlya HTTP-endpointov.

    Ispolzuetsya /ester/thinking/manifest i /ester/thinking/check.
    Ne delaet setevykh vyzovov i ne trogaet globalnoe sostoyanie."""
    if manifest is None:
        manifest = build_manifest()

    return {
        "ok": bool(manifest.get("ok", True)),
        "status": manifest.get("status", {}),
        "modules": manifest.get("modules", {}),
        "coverage": float(manifest.get("coverage", 0.0)),
        "summary": human_report(manifest),
    }