# -*- coding: utf-8 -*-
"""routes/self_codegen_routes.py - REST API dlya "samomodifikatsii" v pesochnitse.

Name:
  Rabochiy stol dlya nabroskov koda: sozdat draft, prognat proverki, primenit,
  pri neobkhodimosti otkatit. All chuvstvitelnye deystviya zaschischeny “pilyuley” (tokenom).

Endpoint:
  • POST /self/codegen/draft {"name","content"} - sozdat draft
  • POST /self/codegen/check {"name"} - zapustit proverki drafta
  • POST /self/codegen/apply {"name"} - primenit proverennyy draft (healthcheck + avto-otkat)
  • POST /self/codegen/revert {"name"} - otkatit primenennyy modul
  • GET /self/codegen/list - perechislit dostupnye drafty
  • GET /metrics/self_codegen - Prometheus metrics

Mosty:
- Yavnyy: (Will ↔ Code) edinyy REST-stol dlya sozdaniya/testirovaniya/aktivatsii moduley.
- Skrytyy #1: (Security ↔ Sandbox) proverki izolirovany v pesochnitse, isklyuchaya pobochnye effekty.
- Skrytyy #2: (Trust ↔ Safeguards) zagruzka moduley s avto-otkatom pri sboe healthcheck.
- Skrytyy #3: (Caution ↔ Pill) chuvstvitelnye operatsii (“apply”, “revert”) trebuyut token-pilyulyu.

Zemnoy abzats:
This is “verstak s zaschitnym ekranom”: polozhil zagotovku, proveril na stanke, podklyuchil -
i pri zhelanii bystro otklyuchil. Uchimsya “lovit rybu” - pishem svoi kryuchki i tut zhe testiruem.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, Response, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_codegen = Blueprint("self_codegen", __name__)

# Soft import of sandbox and pill verifier
try:  # pragma: no cover
    from modules.self.code_sandbox import (  # type: ignore
        draft as _draft,
        check as _check,
        apply as _apply,
        revert as _revert,
        list_all as _list,
        counters as _cnt,
    )
    from modules.caution.pill import verify as _verify_pill  # type: ignore
except Exception:  # pragma: no cover
    _draft = _check = _apply = _revert = _list = _cnt = _verify_pill = None  # type: ignore


def _pill_ok(req, pattern: str) -> bool:
    """Checking the protective “pill” (token) for dangerous operations."""
    if _verify_pill is None:
        return False  # fail-closed
    tok = (req.args.get("pill") or "").strip()
    if not tok:
        return False
    try:
        rep = _verify_pill(tok, pattern=pattern, method=req.method)
        return bool(rep.get("ok"))
    except Exception:
        return False


def register(app):  # pragma: no cover
    app.register_blueprint(bp_codegen)


def init_app(app):  # pragma: no cover
    app.register_blueprint(bp_codegen)


@bp_codegen.post("/self/codegen/draft")
def api_draft():
    """Sozdat novyy draft koda."""
    if _draft is None:
        return jsonify({"ok": False, "error": "code_sandbox_unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    name = str(data.get("name") or "").strip()
    content = str(data.get("content") or "")
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    try:
        return jsonify(_draft(name, content))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_codegen.post("/self/codegen/check")
def api_check():
    """Run checks (tests/lint) for the draft."""
    if _check is None:
        return jsonify({"ok": False, "error": "code_sandbox_unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    try:
        return jsonify(_check(name))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_codegen.post("/self/codegen/apply")
def api_apply():
    """Apply a verified draft (secure operation)."""
    if not _pill_ok(request, pattern=r"^/self/codegen/apply$"):
        return jsonify({"ok": False, "error": "pill_required"}), 403
    if _apply is None:
        return jsonify({"ok": False, "error": "code_sandbox_unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    try:
        return jsonify(_apply(name))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_codegen.post("/self/codegen/revert")
def api_revert():
    """Rollback a previously applied module (protected operation)."""
    if not _pill_ok(request, pattern=r"^/self/codegen/revert$"):
        return jsonify({"ok": False, "error": "pill_required"}), 403
    if _revert is None:
        return jsonify({"ok": False, "error": "code_sandbox_unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    try:
        return jsonify(_revert(name))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_codegen.get("/self/codegen/list")
def api_list():
    """Spisok dostupnykh draftov."""
    if _list is None:
        return jsonify({"ok": False, "error": "code_sandbox_unavailable"}), 500
    try:
        return jsonify(_list())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_codegen.get("/metrics/self_codegen")
def metrics():
    """Metriki Prometheus (text/plain, exposition 0.0.4)."""
    c = _cnt() if callable(_cnt) else {}
    body = (
        f"self_codegen_drafts_total {c.get('drafts_total', 0)}\n"
        f"self_codegen_checks_total {c.get('checks_total', 0)}\n"
        f"self_codegen_applies_ok {c.get('applies_ok', 0)}\n"
        f"self_codegen_applies_fail {c.get('applies_fail', 0)}\n"
        f"self_codegen_reverts_total {c.get('reverts_total', 0)}\n"
    )
    return Response(body, headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})


__all__ = ["bp_codegen", "register", "init_app"]
# c=a+b