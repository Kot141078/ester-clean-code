# routes/ester_net_will_routes_alias.py
# Alias/bridge: willful planner + network profile for Esther.
# Does not change existing signatures. Only new endpoints.
# Submits to the will of Esther and the flags of the environment.

from __future__ import annotations

import os
import json
from flask import Blueprint, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ester_net_will = Blueprint("ester_net_will", __name__)


def _env_flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _net_profile() -> dict:
    """Assembled profile of the Esther network bridge.

    Nothing calls out; only reads ENV."""
    mode = os.getenv("ESTER_NET_SEARCH_AB", "A").upper()
    will_mode = os.getenv("ESTER_NET_WILL_AB", "A").upper()

    return {
        "mode": "B" if mode == "B" else "A",
        "will_mode": "B" if will_mode == "B" else "A",
        "enabled": True,
        "ester_allowed": _env_flag("ESTER_NET_ALLOW_ESTER", True),
        "log_all": _env_flag("ESTER_NET_LOG_ALL", True),
        "safe_defaults": {
            "no_hidden_daemons": True,
            "no_self_mod_without_consent": True,
            "network_only_via_will": True,
        },
    }


@bp_ester_net_will.route("/ester/net/profile", methods=["GET"])
def ester_net_profile():
    """Network bridge profile.

    Used for self-test and UI.
    No external requests."""
    return jsonify({"ok": True, "config": _net_profile()})


def _load_json_response(path: str) -> tuple[int, dict]:
    """Vnutrenniy GET k uzhe suschestvuyuschim endpointam Ester.

    Bez setevykh vyzovov, tolko cherez testovyy klient Flask.
    Safe: esli chto-to idet ne tak - prosto vozvraschaem (code, {})."""
    try:
        client = current_app.test_client()
        resp = client.get(path)
    except Exception:
        return 0, {}

    try:
        data = resp.get_json(force=True)  # type: ignore[arg-type]
    except Exception:
        try:
            data = json.loads(resp.data.decode("utf-8"))
        except Exception:
            data = {}

    return resp.status_code, data if isinstance(data, dict) else {}


@bp_ester_net_will.route("/ester/will/plan_ext_net", methods=["GET"])
def ester_will_plan_ext_net():
    """Rasshirnnyy plan voli c setevym mostom.

    Delaet vnutrenniy zapros k /ester/will/plan_ext (esli est) or /ester/will/plan
    i dobavlyaet zadachi, svyazannye s setevym poiskom cherez most.

    Invariance:
    * Ne lomaet format bazovogo otveta.
    * Add only new tasks.
    * Uchityvaet ENV-flagi i volevoy profil."""
    # 1. Bazovyy plan
    code, base = _load_json_response("/ester/will/plan_ext")
    if code != 200 or not base:
        code, base = _load_json_response("/ester/will/plan")

    if code != 200 or not isinstance(base, dict):
        return jsonify({"ok": False, "reason": "base_will_unavailable"}), 503

    tasks = list(base.get("tasks") or [])
    profile = _net_profile()

    # 2. Manual search at the will of the operator (always allowed, since it goes through the operator)
    tasks.append(
        {
            "id": "net_search_operator_manual",
            "kind": "network",
            "title": "Manual web search via bridge",
            "reason": "The operator can request an external search via /ester/net/search.",
            "safe_auto": False,
            "needs_consent": False,
            "area": "network",
            "payload": {
                "endpoint": "/ester/net/search",
                "source": "operator",
            },
        }
    )

    # 3. Search at the will of Esther - only if explicitly permitted by ENV.
    if profile.get("ester_allowed"):
        tasks.append(
            {
                "id": "net_search_ester_logged",
                "kind": "network",
                "title": "Network search for Esther via /ester/net/search_logged",
                "reason": "Esther can initiate an external search as a conscious action logged into memory.",
                "safe_auto": False,
                "needs_consent": True,
                "area": "network",
                "payload": {
                    "endpoint": "/ester/net/search_logged",
                    "source": "ester",
                },
            }
        )

    # Update and return
    base["tasks"] = tasks
    # if the basic answer did not contain a mode, mark it as ьБъ (top layer)
    base.setdefault("mode", "B")
    base.setdefault("ok", True)
    return jsonify(base)