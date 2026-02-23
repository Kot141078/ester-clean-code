# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Dict, List, Sequence


# SINGLE SOURCE OF TRUTH for route registration list.
ROUTE_MODULES: Sequence[str] = [
    # safety / sanity
    "app_plugins.after_response_sanity",
    "routes._wsgi_guard_fix",
    # core
    "routes.health_routes",
    "routes.docs_routes",
    "routes.memory_routes",
    "routes.mem_kg_routes",
    "routes.research_routes",
    "routes.routes_trace",
    # Iter18-20 runtime/perimeter
    "routes.dreams_routes",
    "routes.initiative_routes",
    "routes.garage_agents_routes",
    "routes.garage_templates_routes",
    "routes.outbox_routes",
    "routes.comm_window_routes",
    "routes.companion_routes",
    "routes.metrics_prom",
    "routes.runtime_ab_routes",
    # messaging
    "routes.telegram_routes",
    "routes.telegram_send_routes",
    "routes.messaging_register_all",
    # optional
    "routes.admin_routes",
    "routes.telemetry_routes",
    "routes.tools_routes",
    "routes.file_routes",
    "routes.mission_routes",
    "routes.whatsapp_routes",
    "routes.chat_api_routes",
    "routes.gta_copilot_routes",
    "routes.retrieval_router_metrics",
    # UI / MVP
    "routes.docs_ui_routes",
    "routes.mvp_manifest_routes",
    "routes.mvp_autonomy_routes",
    "routes.admin_portable_firststart",
    "routes.admin_portable_links",
    "routes.admin_portable_metrics",
    "routes.admin_portable_files",
    "routes.admin_retrieval_router_metrics",
    "routes.admin_branch_residue",
    "routes.admin_identity",
    "routes.admin_settings_ui",
    "routes.admin_vault_keys",
]


def _split_csv(value: str) -> List[str]:
    out: List[str] = []
    for part in (value or "").split(","):
        part = part.strip()
        if part:
            out.append(part)
    return out


def _casefold_key(s: str) -> str:
    return (s or "").strip().casefold()


def get_route_modules(strict: bool = False) -> List[str]:
    """
    Return canonical route module list with env extension.
    strict=False: dedup by casefold (keep first).
    strict=True: raise ValueError on casefold duplicates.
    """
    base = list(ROUTE_MODULES)
    extra = os.getenv("ESTER_EXTRA_ROUTE_MODULES", "").strip()
    if extra:
        base.extend(_split_csv(extra))

    seen: Dict[str, str] = {}
    dups: Dict[str, List[str]] = {}
    out: List[str] = []

    for mod in base:
        mod = (mod or "").strip()
        if not mod:
            continue
        key = _casefold_key(mod)
        if key in seen:
            dups.setdefault(key, [seen[key]]).append(mod)
            if not strict:
                continue
        else:
            seen[key] = mod
        out.append(mod)

    if strict and dups:
        parts: List[str] = []
        for key, vals in sorted(dups.items(), key=lambda kv: kv[0]):
            parts.append(f"{key}: {vals}")
        raise ValueError("Duplicate route modules (casefold): " + "; ".join(parts))

    return out
