# -*- coding: utf-8 -*-
"""routes/mail_compose_routes.py - predprosmotr pisem s rashirnnymi auditoriyami.

MOSTY:
- (Yavnyy) /mail/compose/preview vozvraschaet gotovyy tekst pisma pod auditoriyu/namerenie.
- (Skrytyy #1) Edinyy stil s messendzherami (intent te zhe, shablony glubzhe).
- (Skrytyy #2) Pri zhelanii mozhno podlozhit vneshnyuyu LLM kak podskazchika, no finalnoe decision lokalno.

ZEMNOY ABZATs:
Daet Ester i Owner bystryy instrument proverki “kak budet zvuchat pismo” dlya advokata, banka, gosorgana i t.d.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, request, jsonify, render_template

from modules.persona_style_ext import choose_style_ext, render_email
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mail_compose_routes", __name__, template_folder="../templates", url_prefix="/mail/compose")

@bp.route("/preview", methods=["POST"])
def preview():
    j = request.get_json(force=True, silent=True) or {}
    audience = (j.get("audience") or "neutral").strip().lower()
    intent = (j.get("intent") or "letter").strip().lower()
    content = (j.get("content") or "").strip()
    style = choose_style_ext(audience, intent)
    text = render_email(audience, intent, content)
    return jsonify({"ok": True, "audience": audience, "intent": intent, "style": style, "text": text})

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("mail_compose_admin.html")

def register(app):
    app.register_blueprint(bp)
    return bp