# routes/ester_net_will_routes_alias.py
# Alias/bridge: volevoy planirovschik + setevoy profil dlya Ester.
# Ne menyaet suschestvuyuschie signatury. Tolko novye endpointy.
# Podchinyaetsya vole Ester i flagam okruzheniya.

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
    """Sobrannyy profil setevogo mosta Ester.

    Nichego ne vyzyvaet naruzhu; tolko chitaet ENV.
    """
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
    """Profile setevogo mosta.

    Ispolzuetsya dlya samoproverki i UI.
    Nikakikh vneshnikh zaprosov.
    """
    return jsonify({"ok": True, "config": _net_profile()})


def _load_json_response(path: str) -> tuple[int, dict]:
    """Vnutrenniy GET k uzhe suschestvuyuschim endpointam Ester.

    Bez setevykh vyzovov, tolko cherez testovyy klient Flask.
    Bezopasno: esli chto-to idet ne tak — prosto vozvraschaem (code, {}).
    """
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
    """Rasshirennyy plan voli c setevym mostom.

    Delaet vnutrenniy zapros k /ester/will/plan_ext (esli est) ili /ester/will/plan
    i dobavlyaet zadachi, svyazannye s setevym poiskom cherez most.

    Invarianty:
    * Ne lomaet format bazovogo otveta.
    * Dobavlyaet tolko novye zadachi.
    * Uchityvaet ENV-flagi i volevoy profil.
    """
    # 1. Bazovyy plan
    code, base = _load_json_response("/ester/will/plan_ext")
    if code != 200 or not base:
        code, base = _load_json_response("/ester/will/plan")

    if code != 200 or not isinstance(base, dict):
        return jsonify({"ok": False, "reason": "base_will_unavailable"}), 503

    tasks = list(base.get("tasks") or [])
    profile = _net_profile()

    # 2. Ruchnoy poisk po vole operatora (vsegda razreshen, t.k. idet cherez operatora)
    tasks.append(
        {
            "id": "net_search_operator_manual",
            "kind": "network",
            "title": "Ruchnoy veb-poisk cherez most",
            "reason": "Operator mozhet zaprosit vneshniy poisk cherez /ester/net/search.",
            "safe_auto": False,
            "needs_consent": False,
            "area": "network",
            "payload": {
                "endpoint": "/ester/net/search",
                "source": "operator",
            },
        }
    )

    # 3. Poisk po vole Ester — tolko esli yavno razresheno ENV.
    if profile.get("ester_allowed"):
        tasks.append(
            {
                "id": "net_search_ester_logged",
                "kind": "network",
                "title": "Setevoy poisk dlya Ester cherez /ester/net/search_logged",
                "reason": "Ester mozhet initsiirovat vneshniy poisk kak osoznannoe deystvie, logiruemoe v pamyat.",
                "safe_auto": False,
                "needs_consent": True,
                "area": "network",
                "payload": {
                    "endpoint": "/ester/net/search_logged",
                    "source": "ester",
                },
            }
        )

    # Obnovlyaem i vozvraschaem
    base["tasks"] = tasks
    # esli bazovyy otvet ne soderzhal mode — pomechaem kak 'B' (verkhniy sloy)
    base.setdefault("mode", "B")
    base.setdefault("ok", True)
    return jsonify(base)