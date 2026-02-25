# routes/ester_net_search_logged_mem_routes_alias.py
# Obertka nad /ester/net/search_logged:
# * test of will (via planner);
# * neat log into memory (if there is a suitable endpoint);
# * ni odin sboy ne lomaet bazovyy kontrakt poiska.

from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, Tuple

from flask import Blueprint, request, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ester_net_search_mem = Blueprint("ester_net_search_logged_mem", __name__)


def _env_flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _call_internal(method: str, path: str, payload: Dict[str, Any] | None = None) -> Tuple[int, Any]:
    """Vnutrenniy HTTP k samomu sebe cherez Flask test_client.

    Nikakogo vneshnego trafika, tolko vnutri protsessa.
    Safe: lyubye oshibki prevraschayutsya v (0, None)."""
    try:
        client = current_app.test_client()
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json=payload or {})
    except Exception:
        return 0, None

    try:
        data = resp.get_json(force=True)  # type: ignore[arg-type]
    except Exception:
        try:
            data = json.loads(resp.data.decode("utf-8"))
        except Exception:
            data = None

    return resp.status_code, data


def _check_will_for_network(source: str) -> bool:
    """Soft check via /ester/vill/plan_is_not (if there is one).

    No hard refusals, just a hint."""
    code, data = _call_internal("GET", "/ester/will/plan_ext_net")
    if code != 200 or not isinstance(data, dict):
        # Fullback: the scheduler was not found - it does not block.
        return False

    tasks = data.get("tasks") or []
    if not isinstance(tasks, list):
        return False

    # Historical trace: we are looking for tasks that resolve networking actions.
    for t in tasks:
        try:
            if not isinstance(t, dict):
                continue
            if t.get("kind") != "network":
                continue
            p = t.get("payload") or {}
            # Minimal consistency check.
            if p.get("source") == source:
                return True
        except Exception:
            continue

    return False


def _try_log_memory(source: str, query: str, items: Any) -> bool:
    """Optionalnyy log v pamyat.

    Nothing wrong:
    * if there is no endpoint, we simply return False;
    *ne logiruem sekrety: only tekst zaprosa i zagolovki rezultatov."""
    if not _env_flag("ESTER_NET_LOG_ALL", True):
        return False

    event = {
        "kind": "net_search",
        "source": source,
        "q": query,
        "ts": time.time(),
        "items_preview": [],
    }

    try:
        if isinstance(items, list):
            for it in items[:5]:
                if not isinstance(it, dict):
                    continue
                event["items_preview"].append(
                    {
                        "title": it.get("title"),
                        "link": it.get("link"),
                    }
                )
    except Exception:
        # We simply ignore any problems with the format.
        pass

    # Trying to find a soft memory endpoint
    for path in ("/ester/memory/events", "/ester/memory/event", "/ester/memory/log"):
        code, _ = _call_internal("POST", path, event)
        if code == 200:
            return True

    return False


@bp_ester_net_search_mem.route("/ester/net/search_logged_mem", methods=["POST"])
def ester_net_search_logged_mem():
    """Rasshirnnyy setevoy poisk cherez most.

    Contract:
    * Vkhod: JSON s polyami q, limit (opts.), source (operator|ester).
    * Output: like /esther/no/search_logged + flags villa_checked and memories_logged.
    * If the base endpoint is unavailable - 400 with ok=false."""
    data = request.get_json(force=True, silent=True) or {}

    query = (data.get("q") or "").strip()
    if not query:
        return jsonify({"ok": False, "reason": "empty_query"}), 400

    source = str(data.get("source") or "operator").strip().lower()
    if source not in ("operator", "ester"):
        return jsonify({"ok": False, "reason": "invalid_source"}), 400

    limit = data.get("limit") or data.get("top_k") or 5

    # Soft test of will
    will_checked = _check_will_for_network(source)

    # Vyzov bazovogo logiruemogo poiska
    base_payload = {
        "q": query,
        "limit": int(limit),
        "source": source,
    }
    code, base = _call_internal("POST", "/ester/net/search_logged", base_payload)
    if code != 200 or not isinstance(base, dict):
        return jsonify(
            {"ok": False, "reason": "bridge_failed", "will_checked": will_checked, "memory_logged": False}
        ), 400

    items = base.get("items") or []
    memory_logged = _try_log_memory(source, query, items)

    # Generates a response
    out = dict(base)
    out["ok"] = bool(base.get("ok", True))
    out.setdefault("mode", os.getenv("ESTER_NET_SEARCH_AB", "B"))
    out["will_checked"] = will_checked
    out["memory_logged"] = memory_logged

    return jsonify(out)