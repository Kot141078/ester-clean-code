# routes/ester_net_bridge_routes_alias.py
"""Net bridge alias for Ester.

Tsel:
- Dat chat_api i prochim modulyam stabilnye tochki vkhoda:
  - /ester/net/search_logged_mem
  - (optsionalno) /ester/net/search, esli esche ne suschestvuet.
- Ne lomat originalnye route ester-net-search / ester-net-search-logged.
- Delat vnutrenniy forvard cherez Flask test_client (bez HTTP-petli v sebya).
- Normalizovat payload so, chtoby raznye vyzovy ("q", "query") rabotali odinakovo.

AB-flag:
    ESTER_NET_BRIDGE_AB = A | B (by default A)

A - bazovyy bezopasnyy rezhim:
    - /ester/net/search_logged_mem → snachala /ester/net/search_logged, potom /ester/net/search.
    - Proksiruet tolko esli tselevoy route suschestvuet.
    - Esli nichego net — vozvraschaet ok=False, no bez 500.

B - experimentalnyy:
    - Povedenie takoe zhe, no logiruet bolshe detaley i dopuskaet rasshirniya.
    - Seychas otlichiy minimum, flag nuzhen kak stop-kran.

Zemnoy abzats:
    Etot fayl — tonkiy adapter mezhdu "voley" Ester vyyti v set (chat_api, net_autobridge)
    i realnym HTTP-dvizhkom poiska (/ester/net/search*, kotoryy mozhet menyatsya).
    Vmesto togo, chtoby vshivat adresa i formaty pryamo v mozg, my vynosim ikh syuda:
    esli v buduschem smenitsya realizatsiya poiska (Google, SerpAPI, lokalnyy indexes),
    pravim tolko etot most, a ne vse myshlenie/pamyat."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, current_app, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

NET_BRIDGE_AB = (os.getenv("ESTER_NET_BRIDGE_AB") or "A").strip().upper() or "A"

BP_NAME = "ester_net_bridge_alias"
bp = Blueprint(BP_NAME, __name__)


def _has_route(app, path: str) -> bool:
    """We check whether the exact route is in the URL map."""
    try:
        for rule in app.url_map.iter_rules():
            if rule.rule == path:
                return True
    except Exception:
        # If something goes wrong, we assume that there is no route (without crashing the application).
        return False
    return False


def _forward_internal(path: str, payload: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], int]]:
    """Delaet vnutrenniy POST na ukazannyy path cherez test_client.

    This is yavnyy most:
    - chat_api i drugie moduli vsegda byut v /ester/net/search_logged_mem;
    - etot adapter vnutri prilozheniya perenapravlyaet vyzov v aktualnyy dvizhok poiska.

    Vozvraschaet (json, status) or None, esli route ne nayden."""
    app = current_app._get_current_object()

    if not _has_route(app, path):
        return None

    # Important: test_client uses the same process, without network loops.
    with app.test_client() as c:
        rv = c.post(path, json=payload)
        status = rv.status_code
        try:
            data = rv.get_json(silent=True) or {}
        except Exception:
            data = {}
        return data, status


def _extract_query(body: Dict[str, Any]) -> str:
    # Supports multiple field name options
    q = (
        body.get("q")
        or body.get("query")
        or body.get("question")
        or body.get("text")
        or ""
    )
    # Insurance: sometimes the request is included in the message
    if not q and isinstance(body.get("message"), str):
        q = body["message"]
    return str(q)


def _normalize_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes the payload:
    - bring the keys to a general form,
    - we don’t break additional fields (seed, source, max_resilts, log_to_memory, etc)."""
    norm = dict(body)
    q = _extract_query(body)
    if q:
        norm.setdefault("q", q)
        norm.setdefault("query", q)
    return norm


@bp.route("/ester/net/search_logged_mem", methods=["POST"])
def ester_net_search_logged_mem_bridge():
    """Glavnyy most dlya autobridge.

    Contract:
    - Prinimaet vse, what shlet chat_api / vneshnie klienty.
    - Pytaetsya vyzvat:
        1) /ester/net/search_logged
        2) /ester/net/search
      through vnutrenniy forward.
    - Normalizuet chastichno otvet pod ozhidaemyy chat_api format:
        { ok: bool, used: "search_logged"|"search"|None, items: [...], error?: str }"""
    body = request.get_json(silent=True) or {}
    norm = _normalize_payload(body)

    # If there is no text at all, it’s not a lie that there was a search.
    if not _extract_query(norm):
        return jsonify(
            ok=False,
            used=None,
            items=[],
            error="no_query",
        ), 400

    # A/B slot for the future: now both branches are identical in logic,
    # but we leave the switch as a stop valve for experiments.
    ab = NET_BRIDGE_AB

    # 1. Probuem /ester/net/search_logged
    target_logged = "/ester/net/search_logged"
    if ab in ("A", "B"):
        forwarded = _forward_internal(target_logged, norm)
    else:
        forwarded = None

    if forwarded is not None:
        data, status = forwarded
        if status == 200 and isinstance(data, dict) and data.get("ok", True):
            items = (
                data.get("items")
                or data.get("results")
                or data.get("data")
                or []
            )
            # We collapse it into the expected format without breaking anything.
            return jsonify(
                ok=True,
                used="search_logged",
                items=items,
                # We leave the original answer nearby for advanced clients.
                raw=data,
            ), 200

    # 2. Follbek na /ester/net/search
    target_plain = "/ester/net/search"
    forwarded = _forward_internal(target_plain, norm)
    if forwarded is not None:
        data, status = forwarded
        if status == 200 and isinstance(data, dict) and data.get("ok", True):
            items = (
                data.get("items")
                or data.get("results")
                or data.get("data")
                or []
            )
            return jsonify(
                ok=True,
                used="search",
                items=items,
                raw=data,
            ), 200

    # If you get here, either there are no routes, or both returned an error.
    # We don’t throw 500 so as not to drop the /chat/message.
    return jsonify(
        ok=False,
        used=None,
        items=[],
        error="bridge_failed",
    ), 200


def _register_optional_search_alias(app):
    """Optionalno sozdaem alias /ester/net/search, esli ego net.
    This is skrytyy most:
    - Pozvolyaet ispolzovat edinyy URL, dazhe esli realnyy dvizhok zhivet v drugom place.
    Seychas on ne navyazyvaetsya, tolko strakhuet ot polomok."""
    if _has_route(app, "/ester/net/search"):
        return  # Nichego ne trogaem

    @bp.route("/ester/net/search", methods=["POST"])
    def ester_net_search_fallback():
        body = request.get_json(silent=True) or {}
        norm = _normalize_payload(body)
        q = _extract_query(norm)
        if not q:
            return jsonify(ok=False, items=[], error="no_query"), 400

        # Here you can install a simple engine (for example, register to an external IP),
        # but by default gives a neutral answer so as not to break expectations.
        return jsonify(
            ok=True,
            used="noop",
            items=[],
            note="search alias active, but no backend configured",
        ), 200


def auto_reg():
    """Avto-registratsiya: vyzyvaetsya iz app.py, ne trogaya suschestvuyuschie registratsii.

    Invariance:
    - Ne sozdaem dublikatov marshrutov.
    - All oshibki vnutri zaglatyvaem, chtoby ne uronit prilozhenie."""
    try:
        from app import app  # type: ignore
    except Exception:
        # If there is no global app, it exits quietly.
        return

    try:
        # Registriruem osnovnoy most.
        if not any(rule.rule == "/ester/net/search_logged_mem" for rule in app.url_map.iter_rules()):
            app.register_blueprint(bp)
            print("[ester-net-bridge/routes-alias] registered /ester/net/search_logged_mem")

        # Optional alias /ester/no/search - only if it’s really empty.
        before = any(rule.rule == "/ester/net/search" for rule in app.url_map.iter_rules())
        _register_optional_search_alias(app)
        after = any(rule.rule == "/ester/net/search" for rule in app.url_map.iter_rules())
        if (not before) and after:
            print("[ester-net-bridge/routes-alias] registered /ester/net/search")
    except Exception as e:
        # Ne ronyaem Ester iz-za mosta.
        print(f"[ester-net-bridge/routes-alias] ERROR auto_reg: {e!r}")