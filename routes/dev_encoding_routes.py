# routes/dev_encoding_routes.py
from __future__ import annotations

from flask import Blueprint, request, jsonify, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("dev_encoding", __name__, url_prefix="/dev/encoding")

try:
    import chardet  # optional
    _has_chardet = True
except Exception:
    chardet = None
    _has_chardet = False


@bp.route("/probe", methods=["GET"])
def probe():
    """GET /dev/encoding/probe?text=EsterZF0ZZrobitsZF1ZZTF-8
    Returns YSON with the received text without eeuKSKS (UTF-8)."""
    text = request.args.get("text", "Ester: proverka UTF-8 🚀")
    info = {
        "ok": True,
        "received": text,
        "len": len(text),
        "has_chardet": _has_chardet,
    }
    if _has_chardet:
        try:
            raw = text.encode("utf-8", errors="replace")
            det = chardet.detect(raw)
            info["chardet"] = {
                "encoding": det.get("encoding"),
                "confidence": float(det.get("confidence") or 0.0),
                "language": det.get("language"),
            }
        except Exception:
            info["chardet"] = {"encoding": None, "confidence": 0.0, "language": None}
    return jsonify(info), 200


@bp.route("/sample_html", methods=["GET"])
def sample_html():
    """HTML page with explicit UTF-8."""
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Kodirovka OK</title>
</head>
<body>
  <h1>Ester: proverka UTF-8 ✅</h1>
  <p>Esli vidite kirillitsu bez krakozyabr - vse khorosho.</p>
</body>
</html>"""
    return Response(html, status=200, headers={"Content-Type": "text/html; charset=utf-8"})


def register(app):
    # We register the blueprint without contacting current_app.
    app.register_blueprint(bp)
    try:
        app.logger.info("dev_encoding_routes: registered /dev/encoding/*")
    except Exception:
        pass