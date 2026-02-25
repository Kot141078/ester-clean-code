# -*- coding: utf-8 -*-
"""Mini-server dlya proverki portal.html s Jinja-renderingom.
Mosty:
- Yavnyy: Flask <-> Jinja.
- Skrytye: (ENV<->put), (shablony<->otdacha).

Zemnoy abzats:
This is “polevoy akkumulyator”, no uzhe s pravilnoy polyarnostyu - Jinja-rashirniya rabotayut.

c=a+b"""
from pathlib import Path
from flask import Flask, render_template
from jinja2 import FileSystemLoader, ChoiceLoader
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = Path(__file__).resolve().parent
TPL = BASE / "templates"
STATIC = BASE / "static"

app = Flask(__name__, template_folder=str(TPL), static_folder=str(STATIC), static_url_path="/static")

# HoicheLoader will back up (if you need several paths)
try:
    old = app.jinja_loader
    app.jinja_loader = ChoiceLoader([old, FileSystemLoader(str(TPL))])
except Exception:
    pass

@app.get("/portal")
def portal():
    return render_template("portal.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8137, debug=False)