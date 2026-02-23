# -*- coding: utf-8 -*-
"""
routes/entity_board_routes.py - doska suschnostey.

MOSTY:
- (Yavnyy) GET /entities/board - HTML-stranitsa; API ispolzuet suschestvuyuschie /mem/entity/*.
- (Skrytyy #1) Pozvolyaet iskat/filtrovat i ssylatsya na /mem/explorer.
- (Skrytyy #2) Ne menyaet format khraneniya - prosto UI-nadstroyka.

ZEMNOY ABZATs:
Katalog «kto/chto»: kartochki person/organizatsiy/dokov - bystro nayti i pereyti v pamyat.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("entity_board_routes", __name__, url_prefix="/entities")

def register(app):
    app.register_blueprint(bp)

@bp.get("/board")
def board():
    return render_template("entity_board.html")
# c=a+b