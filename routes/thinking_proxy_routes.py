# -*- coding: utf-8 -*-
"""
routes/thinking_proxy_routes.py - nebolshie diagnosticheskie endpointy dlya
proverki, chto «thinking» korrektno podkhvatilsya i rabotaet.
Bezopasnost: eto tolko debug-info, ne izmenyaet sostoyanie. Razreshayte
dostup cherez RBAC/ENV po vashemu tekuschemu rezhimu (v dev - svobodno).

Drop-in: signatury app.register_routes(app) sokhraneny kak vo vsekh routes.
"""
from __future__ import annotations
from flask import Blueprint, jsonify, render_template  # type: ignore
import importlib, time, traceback
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint('thinking_diag', __name__, url_prefix='/debug/thinking')

@bp.get('/ping')
def ping():
    info = {
        'ok': True,
        'ts': int(time.time()),
    }
    try:
        thinking = importlib.import_module('thinking')
        # poprobuem podtyanut chasto ispolzuemye chasti
        try:
            think_core = importlib.import_module('thinking.think_core')
            info['think_core_loaded'] = True
            eng_name = getattr(think_core, 'ENGINE_NAME', None)
            if eng_name:
                info['engine'] = eng_name
        except Exception as e:
            info['think_core_loaded'] = False
            info['think_core_error'] = f'{type(e).__name__}: {e}'
        # nalichie action_registry
        try:
            act = importlib.import_module('thinking.action_registry')
            info['action_registry_loaded'] = True
            counts = {}
            for key in ('_REGISTRY', 'REGISTRY', 'registry'):
                if hasattr(act, key):
                    val = getattr(act, key)
                    try:
                        counts['registered'] = len(val)
                    except Exception:
                        counts['registered'] = f'type={type(val).__name__}'
                    break
            if counts:
                info['registry'] = counts
        except Exception as e:
            info['action_registry_loaded'] = False
            info['action_registry_error'] = f'{type(e).__name__}: {e}'
    except Exception as e:
        info['ok'] = False
        info['error'] = f'{type(e).__name__}: {e}'
        info['tb'] = traceback.format_exc(limit=3)
    return jsonify(info)

# Nebolshaya stranitsa s vyvodom JSON dlya udobstva v brauzere
@bp.get('/ui')
def ui_page():
    return render_template('thinking/status.html')

def register_routes(app):
    app.register_blueprint(bp)


def register(app):
    app.register_blueprint(bp)
    return app