# -*- coding: utf-8 -*-
"""
routes/error_helpers.py - edinoe mesto dlya myagkikh operatsionnykh podskazok.
- RuntimeError s klyuchevymi slovami OCR → druzhelyubnyy otvet i ssylka na /ops/ingest/help
- Inye RuntimeError → akkuratnyy JSON bez stekov.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_error = Blueprint("error_helpers", __name__)


def _is_ocr_runtime(err: RuntimeError) -> bool:
    msg = (str(err) or "").lower()
    keys = ["tesseract", "pdf2image", "poppler", "ocr required", "pytesseract"]
    return any(k in msg for k in keys)


@bp_error.app_errorhandler(RuntimeError)
def handle_runtime_error(err: RuntimeError):
    """
    Unifitsirovannaya obrabotka RuntimeError:
      - OCR-zavisimosti → html/help ili json/hint
      - prochee → kompaktnyy JSON bez trassy
    """
    if _is_ocr_runtime(err):
        # HTML dlya UI i JSON dlya API (content negotiation)
        wants_html = "text/html" in (request.headers.get("Accept") or "")
        payload = {
            "ok": False,
            "error": "ocr_dependency_missing",
            "hint": "Ustanovite tesseract/pdf2image (sm. /ops/ingest/help)",
            "help_url": "/ops/ingest/help",
        }
        if wants_html:
            return render_template("ops_ingest_help.html"), 200
        return jsonify(payload), 400

    # Obschiy sluchay - bez lishnikh podrobnostey
    return jsonify({"ok": False, "error": "runtime_error", "message": str(err)}), 400


def register_error_helpers(app) -> None:  # pragma: no cover
    """Drop-in registratsiya blyuprinta s obrabotchikami oshibok."""
    app.register_blueprint(bp_error)


# Sovmestimye khuki i eksport - po konventsii proekta
def register(app):  # pragma: no cover
    app.register_blueprint(bp_error)


def init_app(app):  # pragma: no cover
    app.register_blueprint(bp_error)


__all__ = ["bp_error", "register_error_helpers", "register", "init_app"]