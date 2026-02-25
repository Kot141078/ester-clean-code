# -*- coding: utf-8 -*-
"""routes/wa_style_admin.py - Mini-UI dlya predprosmotra i bezopasnoy (dry-run) otpravki WA-soobscheniy.

MOSTY:
- (Yavnyy) Web-stranitsa dlya operatorov/Owner: vybrat auditoriyu/namerenie i uvidet itogovyy tekst.
- (Skrytyy #1) Validatsiya stilya cherez suschestvuyuschiy API /wa/ctrl/api/style/preview.
- (Skrytyy #2) Bezopasnaya otpravka cherez /wa/send?dry_run=1 (ne ukhodit naruzhu bez tokenov).

ZEMNOY ABZATs:
Eto “pult” dlya ruchnoy proverki “chelovechnosti” i tona pered masshtabnoy rassylkoy or avtoproaktivnostyu.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint(
    "wa_style_admin",
    __name__,
    template_folder="../templates",
    static_folder=None,
    url_prefix="/wa/style"
)

@bp.route("/admin", methods=["GET"])
def admin_page():
    # A simple page - everything else is done by AJAX using existing APIs.
    return render_template("wa_style_admin.html")


def register(app):
    app.register_blueprint(bp)
    return bp