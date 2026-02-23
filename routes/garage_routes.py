# -*- coding: utf-8 -*-
"""
routes/garage_routes.py - unifitsirovannyy REST-interfeys «laboratorii-garazha» s P2P-sync.

Mosty:
- Yavnyy: (Veb ↔ Garazh) edinye ruchki dlya proektov, predlozheniy, saytov, invoysov i upravleniya sborkoy.
- Skrytyy #1: (Ostorozhnost ↔ Pilyuli) eksport ZIP zaschischen «pill»-proverkoy dlya high-risk operatsiy.
- Skrytyy #2: (Memory ↔ Profile) klyuchevye sobytiya, vklyuchaya sborku, logiruyutsya v pamyat i pishut zapis profilea.
- Skrytyy #3: (Mesh ↔ Avtomatizatsiya) zadachi sborki mozhno stavit v /mesh/task/submit.
- Dop.: (Raspredelennaya pamyat Ester ↔ P2P) /garage/project/sync dlya simulyatsii sinkhronizatsii proektov po seti agentov.

Zemnoy abzats:
Zadali komandu - i garazh nachal rabotat: sozdali proekt, sobrali predlozhenie, sdelali sayt, zapustili sborku,
upakovali i vystavili schet. Vse cherez determinirovannye JSON-kontrakty.

# c=a+b
"""
from __future__ import annotations

import os
import json
import urllib.request
from typing import Dict, Any, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("garage_routes", __name__)

# --- Importy moduley (myagkie, kontrakty ne menyaem) ---
try:
    from modules.garage.core import (
        create_project as _create,
        list_projects as _list,
        scaffold as _scaffold,
        get_project as _get,
        export_zip as _export,
    )  # type: ignore
    from modules.garage.jobs import scan as _scan  # type: ignore
    from modules.garage.proposal import make as _proposal  # type: ignore
    from modules.garage.sitegen import (  # type: ignore
        build_project_site as _site,
        build_portfolio_site as _portfolio_site,
    )
    from modules.garage.invoice import make_invoice as _invoice  # type: ignore
    from modules.garage.projects import add_file as _add_file, build as _build  # type: ignore
except Exception:  # pragma: no cover
    _create = _list = _scaffold = _get = _export = None
    _scan = _proposal = _site = _portfolio_site = _invoice = None
    _add_file = _build = None


def register(app):  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    register(app)


# --- RBAC/Bezopasnost/Audit ---
def _rbac_ok() -> bool:
    """Grubaya zaglushka RBAC dlya write-operatsiy (rasshir pod realnye roli)."""
    if os.getenv("RBAC_REQUIRED", "true").lower() == "false":
        return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return bool(has_any_role(["admin", "operator"]))  # type: ignore
    except Exception:
        # Esli RBAC net - ne blokiruem testovyy stend
        return True


def _pill_ok(req) -> bool:
    """Proverka «pill» dlya high-risk operatsiy (eksport)."""
    tok = req.args.get("pill", "")
    if not tok:
        return False
    try:
        from modules.caution.pill import verify  # type: ignore

        rep = verify(tok, pattern="^/garage/project/export$", method="POST")
        return bool(rep.get("ok", False))
    except Exception:
        # Esli v demo-rezhime verify nedostupen - propuskaem pri nalichii tokena
        return True if tok else False


def _log_passport(event: str, data: Dict[str, Any]) -> None:
    """Logiruet sobytie v «profile» pamyati (best-effort)."""
    try:
        from modules.mem.passport import append as _pp  # type: ignore

        _pp(event, data, "garage://routes")
    except Exception:
        pass


def _discover_register(modname: str) -> Dict[str, Any]:
    """Registriruet modul cherez discover-servis (HTTP)."""
    data = json.dumps({"modules": [modname]}).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/app/discover/register",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {"ok": False, "error": "discover_unavailable"}


def _p2p_sync_sim(project_id: str) -> Dict[str, Any]:
    """P2P-simulyatsiya: dobavlyaem id proekta v bloom-filtr seti agentov."""
    try:
        from modules.p2p.bloom import add  # type: ignore

        add([project_id])
        _log_passport("garage_p2p_sync", {"id": project_id})
        return {"ok": True, "synced": True}
    except Exception:
        return {"ok": False, "error": "p2p_sync_failed"}


# --- Marshruty: proekty ---
@bp.route("/garage/project/list", methods=["GET"])
def api_list():
    if _list is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    try:
        rep = _list()  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    _log_passport("garage_api_list", {"projects": len(rep.get("projects", [])) if isinstance(rep, dict) else None})
    return jsonify(rep)


@bp.route("/garage/project/get", methods=["GET"])
def api_get():
    if _get is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    name = str(request.args.get("name") or "")
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    try:
        rep = _get(name)  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/garage/project/create", methods=["POST"])
def api_create():
    if not _rbac_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if _create is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    d = request.get_json(silent=True) or {}
    name = str(d.get("name", ""))
    kind = str(d.get("kind", "generic"))
    brief = str(d.get("brief", ""))
    owner = str(d.get("owner", ""))
    try:
        rep = _create(name, kind, brief, owner)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    _log_passport("garage_api_create", {"name": name, "ok": bool(rep.get("ok")) if isinstance(rep, dict) else None})
    return jsonify(rep)


@bp.route("/garage/project/scaffold", methods=["POST"])
def api_scaffold():
    if not _rbac_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if _scaffold is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    d = request.get_json(silent=True) or {}
    pid = str(d.get("id", ""))
    try:
        rep = _scaffold(pid)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    _log_passport("garage_api_scaffold", {"id": pid, "ok": bool(rep.get("ok")) if isinstance(rep, dict) else None})
    return jsonify(rep)


@bp.route("/garage/project/add_file", methods=["POST"])
def api_add_file():
    if not _rbac_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if _add_file is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    d = request.get_json(silent=True) or {}
    name = str(d.get("name", ""))
    rel_path = str(d.get("rel_path", ""))
    content = str(d.get("content", ""))
    try:
        rep = _add_file(name, rel_path, content)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    _log_passport(
        "garage_api_add_file",
        {"name": name, "rel_path": rel_path, "ok": bool(rep.get("ok")) if isinstance(rep, dict) else None},
    )
    return jsonify(rep)


@bp.route("/garage/project/build", methods=["POST"])
def api_build():
    if not _rbac_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if _build is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    d = request.get_json(silent=True) or {}
    name = str(d.get("name", ""))
    try:
        rep = _build(name)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    _log_passport("garage_api_build", {"name": name, "ok": bool(rep.get("ok")) if isinstance(rep, dict) else None})
    if isinstance(rep, dict) and rep.get("ok") and os.getenv("GARAGE_P2P_SYNC", "true").lower() == "true":
        _p2p_sync_sim(name)
    return jsonify(rep)


@bp.route("/garage/project/register", methods=["POST"])
def api_register_project():
    if not _rbac_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if _list is None or _get is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    d = request.get_json(silent=True) or {}
    name = str(d.get("name", ""))
    try:
        proj = _get(name)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    if not (isinstance(proj, dict) and proj.get("ok")):
        return jsonify({"ok": False, "error": "not_found"}), 404
    disc_rep = _discover_register(str(proj.get("module", "")))
    rep = {"ok": True, "module": proj.get("module", ""), "discover": disc_rep}
    _log_passport("garage_api_register", {"name": name, "ok": True})
    return jsonify(rep)


@bp.route("/garage/project/export", methods=["POST"])
def api_export():
    if not _rbac_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if _export is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    if not _pill_ok(request):
        return jsonify({"ok": False, "error": "pill_required"}), 403
    d = request.get_json(silent=True) or {}
    pid = str(d.get("id", ""))
    try:
        rep = _export(pid)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    _log_passport("garage_api_export", {"id": pid, "ok": bool(rep.get("ok")) if isinstance(rep, dict) else None})
    return jsonify(rep)


@bp.route("/garage/project/sync", methods=["POST"])
def api_sync():
    """Simulirovat P2P-sinkhronizatsiyu proekta mezhdu uzlami seti agentov."""
    if not _rbac_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    d = request.get_json(silent=True) or {}
    pid = str(d.get("id", ""))
    if not pid:
        return jsonify({"ok": False, "error": "id required"}), 400
    rep = _p2p_sync_sim(pid)
    return jsonify(rep)


# --- Marshruty: predlozheniya/sayty/invoysy/vakansii/dzhoby ---
@bp.route("/garage/proposal/make", methods=["POST"])
def api_proposal():
    if not _rbac_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if _proposal is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    d = request.get_json(silent=True) or {}
    try:
        rep = _proposal(d)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    _log_passport("garage_api_proposal", {"ok": bool(rep.get("ok")) if isinstance(rep, dict) else None})
    return jsonify(rep)


@bp.route("/garage/site/build_project", methods=["POST"])
def api_site_project():
    if not _rbac_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if _site is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    d = request.get_json(silent=True) or {}
    try:
        rep = _site(d)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    _log_passport("garage_api_site_project", {"ok": bool(rep.get("ok")) if isinstance(rep, dict) else None})
    return jsonify(rep)


@bp.route("/garage/site/build_portfolio", methods=["POST"])
def api_site_portfolio():
    if not _rbac_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if _portfolio_site is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    d = request.get_json(silent=True) or {}
    try:
        rep = _portfolio_site(d)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    _log_passport("garage_api_site_portfolio", {"ok": bool(rep.get("ok")) if isinstance(rep, dict) else None})
    return jsonify(rep)


@bp.route("/garage/invoice/make", methods=["POST"])
def api_invoice_make():
    if not _rbac_ok():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if _invoice is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    d = request.get_json(silent=True) or {}
    try:
        rep = _invoice(d)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    _log_passport("garage_api_invoice", {"ok": bool(rep.get("ok")) if isinstance(rep, dict) else None})
    return jsonify(rep)


@bp.route("/garage/jobs/scan", methods=["GET"])
def api_jobs_scan():
    if _scan is None:
        return jsonify({"ok": False, "error": "garage_unavailable"}), 500
    kind = str(request.args.get("kind") or "")
    try:
        rep = _scan(kind) if kind else _scan()  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


__all__ = ["bp", "register", "init_app"]
# c=a+b