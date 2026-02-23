# routes/ester_net_bridge_routes_alias.py
"""
Net bridge alias for Ester.

Tsel:
- Dat chat_api i prochim modulyam stabilnye tochki vkhoda:
  - /ester/net/search_logged_mem
  - (optsionalno) /ester/net/search, esli esche ne suschestvuet.
- Ne lomat originalnye marshruty ester-net-search / ester-net-search-logged.
- Delat vnutrenniy forvard cherez Flask test_client (bez HTTP-petli v sebya).
- Normalizovat payload tak, chtoby raznye vyzovy ("q", "query") rabotali odinakovo.

AB-flag:
    ESTER_NET_BRIDGE_AB = A | B   (po umolchaniyu A)

A — bazovyy bezopasnyy rezhim:
    - /ester/net/search_logged_mem → snachala /ester/net/search_logged, potom /ester/net/search.
    - Proksiruet tolko esli tselevoy marshrut suschestvuet.
    - Esli nichego net — vozvraschaet ok=False, no bez 500.

B — eksperimentalnyy:
    - Povedenie takoe zhe, no logiruet bolshe detaley i dopuskaet rasshireniya.
    - Seychas otlichiy minimum, flag nuzhen kak stop-kran.

Zemnoy abzats:
    Etot fayl — tonkiy adapter mezhdu "voley" Ester vyyti v set (chat_api, net_autobridge)
    i realnym HTTP-dvizhkom poiska (/ester/net/search*, kotoryy mozhet menyatsya).
    Vmesto togo, chtoby vshivat adresa i formaty pryamo v mozg, my vynosim ikh syuda:
    esli v buduschem smenitsya realizatsiya poiska (Google, SerpAPI, lokalnyy indeks),
    pravim tolko etot most, a ne vse myshlenie/pamyat.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, current_app, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

NET_BRIDGE_AB = (os.getenv("ESTER_NET_BRIDGE_AB") or "A").strip().upper() or "A"

BP_NAME = "ester_net_bridge_alias"
bp = Blueprint(BP_NAME, __name__)


def _has_route(app, path: str) -> bool:
    """Proveryaem, est li v karte URL tochnyy marshrut."""
    try:
        for rule in app.url_map.iter_rules():
            if rule.rule == path:
                return True
    except Exception:
        # Esli chto-to poshlo ne tak — schitaem, chto marshruta net (bez padeniya prilozheniya).
        return False
    return False


def _forward_internal(path: str, payload: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], int]]:
    """
    Delaet vnutrenniy POST na ukazannyy path cherez test_client.

    Eto yavnyy most:
    - chat_api i drugie moduli vsegda byut v /ester/net/search_logged_mem;
    - etot adapter vnutri prilozheniya perenapravlyaet vyzov v aktualnyy dvizhok poiska.

    Vozvraschaet (json, status) ili None, esli marshrut ne nayden.
    """
    app = current_app._get_current_object()

    if not _has_route(app, path):
        return None

    # Vazhno: test_client ispolzuet tot zhe protsess, bez setevykh petel.
    with app.test_client() as c:
        rv = c.post(path, json=payload)
        status = rv.status_code
        try:
            data = rv.get_json(silent=True) or {}
        except Exception:
            data = {}
        return data, status


def _extract_query(body: Dict[str, Any]) -> str:
    # Podderzhivaem neskolko variantov imeni polya
    q = (
        body.get("q")
        or body.get("query")
        or body.get("question")
        or body.get("text")
        or ""
    )
    # Strakhovka: inogda zapros kladut v message
    if not q and isinstance(body.get("message"), str):
        q = body["message"]
    return str(q)


def _normalize_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizuem payload:
    - privodim klyuchi q/query k obschemu vidu,
    - ne lomaem dopolnitelnye polya (sid, source, max_results, log_to_memory, etc).
    """
    norm = dict(body)
    q = _extract_query(body)
    if q:
        norm.setdefault("q", q)
        norm.setdefault("query", q)
    return norm


@bp.route("/ester/net/search_logged_mem", methods=["POST"])
def ester_net_search_logged_mem_bridge():
    """
    Glavnyy most dlya autobridge.

    Kontrakt:
    - Prinimaet vse, chto shlet chat_api / vneshnie klienty.
    - Pytaetsya vyzvat:
        1) /ester/net/search_logged
        2) /ester/net/search
      cherez vnutrenniy forvard.
    - Normalizuet chastichno otvet pod ozhidaemyy chat_api format:
        { ok: bool, used: "search_logged"|"search"|None, items: [...], error?: str }
    """
    body = request.get_json(silent=True) or {}
    norm = _normalize_payload(body)

    # Esli voobsche net teksta — ne vrem, chto poisk byl.
    if not _extract_query(norm):
        return jsonify(
            ok=False,
            used=None,
            items=[],
            error="no_query",
        ), 400

    # A/B slot na buduschee: seychas obe vetki identichny po logike,
    # no ostavlyaem pereklyuchatel kak stop-kran dlya eksperimentov.
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
            # Skhlopyvaem v ozhidaemyy format, nichego ne lomaya.
            return jsonify(
                ok=True,
                used="search_logged",
                items=items,
                # Ostavlyaem originalnyy otvet ryadom dlya prodvinutykh klientov.
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

    # Esli dobralis syuda — libo marshrutov net, libo oba vernuli oshibku.
    # Ne kidaem 500, chtoby ne ronyat /chat/message.
    return jsonify(
        ok=False,
        used=None,
        items=[],
        error="bridge_failed",
    ), 200


def _register_optional_search_alias(app):
    """
    Optsionalno sozdaem alias /ester/net/search, esli ego net.
    Eto skrytyy most:
    - Pozvolyaet ispolzovat edinyy URL, dazhe esli realnyy dvizhok zhivet v drugom meste.
    Seychas on ne navyazyvaetsya, tolko strakhuet ot polomok.
    """
    if _has_route(app, "/ester/net/search"):
        return  # Nichego ne trogaem

    @bp.route("/ester/net/search", methods=["POST"])
    def ester_net_search_fallback():
        body = request.get_json(silent=True) or {}
        norm = _normalize_payload(body)
        q = _extract_query(norm)
        if not q:
            return jsonify(ok=False, items=[], error="no_query"), 400

        # Zdes mozhno povesit prostoy dvizhok (napr. requests k vneshnemu API),
        # no po umolchaniyu daem neytralnyy otvet, chtoby ne lomat ozhidaniya.
        return jsonify(
            ok=True,
            used="noop",
            items=[],
            note="search alias active, but no backend configured",
        ), 200


def auto_reg():
    """
    Avto-registratsiya: vyzyvaetsya iz app.py, ne trogaya suschestvuyuschie registratsii.

    Invarianty:
    - Ne sozdaem dublikatov marshrutov.
    - Vse oshibki vnutri zaglatyvaem, chtoby ne uronit prilozhenie.
    """
    try:
        from app import app  # type: ignore
    except Exception:
        # Esli net globalnogo app — tikho vykhodim.
        return

    try:
        # Registriruem osnovnoy most.
        if not any(rule.rule == "/ester/net/search_logged_mem" for rule in app.url_map.iter_rules()):
            app.register_blueprint(bp)
            print("[ester-net-bridge/routes-alias] registered /ester/net/search_logged_mem")

        # Optsionalnyy alias /ester/net/search — tolko esli realno pusto.
        before = any(rule.rule == "/ester/net/search" for rule in app.url_map.iter_rules())
        _register_optional_search_alias(app)
        after = any(rule.rule == "/ester/net/search" for rule in app.url_map.iter_rules())
        if (not before) and after:
            print("[ester-net-bridge/routes-alias] registered /ester/net/search")
    except Exception as e:
        # Ne ronyaem Ester iz-za mosta.
        print(f"[ester-net-bridge/routes-alias] ERROR auto_reg: {e!r}")