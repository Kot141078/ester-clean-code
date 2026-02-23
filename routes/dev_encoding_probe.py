# -*- coding: utf-8 -*-
"""
routes/dev_encoding_probe.py - vspomogatelnye proverki kodirovki.

MOSTY:
- (Yavnyy) /dev/encoding/probe - JSON-ekho stroki; /dev/encoding/sample_html - HTML so <meta charset>.
- (Skrytyy #1) Diagnostika «po vozdukhu» bez lazaniya v fayly/logi.
- (Skrytyy #2) Mozhno vstraivat v avtotesty/health.

ZEMNOY ABZATs:
Esli gde-to vse esche «krakozyabry», etimi endpointami mozhno bystro ponyat:
bitye bayty na servere ili klient neverno chitaet.
"""

from __future__ import annotations
from flask import Blueprint, request, jsonify, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("dev_encoding_probe", __name__)

@bp.get("/dev/encoding/probe")
def dev_encoding_probe():
    text = request.args.get("text", "Ester: proverka UTF-8 ✓")
    info = {
        "echo": text,
        "length": len(text),
        "codepoints": [ord(ch) for ch in text[:8]],
    }
    r = jsonify(info)
    # zagolovok uzhe propatchen globalno, no yavno ne povredit
    r.headers["Content-Type"] = "application/json; charset=utf-8"
    return r

@bp.get("/dev/encoding/sample_html")
def dev_encoding_sample_html():
    html = """<!doctype html><html><head>
<meta charset="utf-8"><title>UTF-8 Sample</title></head>
<body>
<p>Ester govorit: «Privet, mir!» - vse dolzhno byt chitabelno.</p>
</body></html>"""
    return Response(html, mimetype="text/html; charset=utf-8")

def register(app):
    app.register_blueprint(bp)
    return bp