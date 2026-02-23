# -*- coding: utf-8 -*-
"""
routes/jinja_loader_alias.py — dobavlyaet vtoroy put shablonov (naprimer, D:\ester-project\templates)

Mosty:
- Yavnyy: (Flask ↔ UI) podklyuchaem vtoroy poiskovyy put dlya shablonov.
- Skrytyy #1: (Sovmestimost ↔ Damp) ne trogaem app.py, ispolzuem standartnyy register().
- Skrytyy #2: (Inzheneriya ↔ Windows/Python) rabotaem s absolyutnymi putyami i ChoiceLoader.

Zemnoy abzats (inzheneriya):
Jinja ischet HTML po «poiskovym putyam». Esli prilozhenie startuet iz paketa, root_path ukhodit v podkatalog,
i shablony na verkhnem urovne ne vidny. My prosto dobavlyaem etot verkhneurovnevyy put v poiskovyy spisok.

c=a+b
"""
from __future__ import annotations
import os
from flask import Blueprint, current_app, jsonify
from jinja2 import ChoiceLoader, FileSystemLoader
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("jinja_loader_alias", __name__)
AB = os.getenv("ESTER_JINJA_LOADER_AB", "B").upper()  # A=off, B=on
EXTRA = os.getenv("ESTER_TEMPLATE_DIR") or os.path.join(os.getcwd(), "templates")

def _apply_loader(app):
    try:
        old = getattr(app, "jinja_loader", None)
        extra = FileSystemLoader(EXTRA, encoding="utf-8")
        if isinstance(old, ChoiceLoader):
            loaders = list(old.loaders)
            # izbegaem dubley
            if not any(getattr(l, "searchpath", None) == [EXTRA] for l in loaders):
                loaders.append(extra)
            app.jinja_loader = ChoiceLoader(loaders)
        elif old is not None:
            app.jinja_loader = ChoiceLoader([old, extra])
        else:
            app.jinja_loader = ChoiceLoader([extra])
        return True
    except Exception:
        return False

@bp.get("/_alias/templates/health")
def health():
    app = current_app
    root = getattr(app, "root_path", os.getcwd())
    paths = []
    ld = getattr(app, "jinja_loader", None)
    try:
        if isinstance(ld, ChoiceLoader):
            for l in ld.loaders:
                paths += getattr(l, "searchpath", [])
        else:
            paths += getattr(ld, "searchpath", [])
    except Exception:
        pass

    def exists(name: str) -> bool:
        for p in paths:
            if os.path.isfile(os.path.join(p, name)):
                return True
        return False

    return jsonify(
        ok=True,
        ab=AB,
        root=root,
        search_paths=paths,
        portal_exists=exists("portal.html"),
        base_exists=exists("_admin_base.html"),
    )

def register(app):
    if AB != "B":
        return False
    if bp.name not in app.blueprints:
        app.register_blueprint(bp)
    _apply_loader(app)
    return True

def init_app(app):  # pragma: no cover
    register(app)

# c=a+b