# -*- coding: utf-8 -*-
"""
Mosty:
- Yavnyy: Flask ↔ fayl portal.html.
- Skrytye: (ENV↔put), (prostaya proverka↔osnovnoy stek).

Zemnoy abzats:
Eto «polevoy akkumulyator»: pitaet portal napryamuyu, minuya slozhnuyu skhemu.

c=a+b
"""
from pathlib import Path
from flask import Flask, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = Path(__file__).resolve().parent
TPL = BASE / "templates" / "portal.html"

app = Flask(__name__)

@app.get("/portal")
def portal():
    if TPL.is_file():
        return Response(TPL.read_text(encoding="utf-8"), mimetype="text/html; charset=utf-8")
    return Response("<h1>portal.html not found</h1>", status=500, mimetype="text/html; charset=utf-8")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8137, debug=False)