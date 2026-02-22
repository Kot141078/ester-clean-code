# -*- coding: utf-8 -*-
"""
Chat-most dlya determinirovannykh tsitat bez LLM.

POST /ester/chat/quote
Telo:
  1) { "pattern": "E2E — ...", "wrap": 1 }
  2) ili { "message": "Naydi «...». Otvet TOLKO ..." } — pattern berem iz «elochek».

Otvet:
  { "ok": true, "answer": "\"...\"" }  ili  { "ok": true, "answer": "NOT_FOUND" }
"""
import re
from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("chat_quote_http", __name__)

_GUILLEMET_RE = re.compile(r"«(.+?)»")

def _extract_pattern(msg: str) -> str:
    if not msg:
        return ""
    m = _GUILLEMET_RE.search(msg)
    return m.group(1).strip() if m else ""

def _quote_once(pattern: str, wrap: bool) -> str:
    """
    Vyzovem chistyy khelper iz rag_docs_extra_http napryamuyu (bez HTTP/Flask-vyzovov).
    """
    try:
        # lokalnyy import, chtoby ne sozdavat zhestkikh tsiklicheskikh zavisimostey pri avtoloade
        from modules.rag import rag_docs_extra_http as extra
    except Exception:
        return "NOT_FOUND"

    line = extra.find_first_line(pattern)
    if not line:
        return "NOT_FOUND"
    return f"\"{line}\"" if wrap else line

@bp.route("/ester/chat/quote", methods=["POST"])
def chat_quote():
    data = request.get_json(silent=True) or {}
    pattern = (data.get("pattern") or "").strip()
    wrap = bool(int(data.get("wrap") or 1))

    if not pattern:
        pattern = _extract_pattern((data.get("message") or "").strip())
    if not pattern:
        return jsonify(ok=False, error="empty pattern (pass 'pattern' or wrap it in «...» via 'message')"), 400

    answer = _quote_once(pattern, wrap)
    return jsonify(ok=True, answer=answer)

def register(app):
    app.register_blueprint(bp)
    print("[chat-quote/routes] registered /ester/chat/quote")