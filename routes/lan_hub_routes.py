
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_bp = Blueprint("lan_hub_routes", __name__)
_AB = os.getenv("ESTER_LANHUB_AB", "B").upper()

def _drive_letter():
    d = os.getenv("ESTER_LANHUB_DRIVE", "Z").strip().rstrip(":")
    return d or "Z"

def _lan_subdir():
    return os.getenv("ESTER_LANHUB_DIR", "ester-data").strip("\/ ")

def _lan_unc():
    return os.getenv("ESTER_LANHUB_UNC", r"\\EsterHub\ester-data")

def _drv_root():
    return f"{_drive_letter()}:\\"

def _lan_root():
    return os.path.join(_drv_root(), _lan_subdir())

def ensure_data_root_fallback():
    """
    If Z: is missing, force local data fallback.
    - Respect ESTER_DATA_ROOT if already set.
    - If PERSIST_DIR is missing, set it relative to ESTER_DATA_ROOT.
    """
    drv = _drv_root()
    lan = _lan_root()
    mounted = os.path.exists(drv)
    ok_lan = mounted and os.path.exists(lan)

    if ok_lan:
        data_root = lan
    else:
        data_root = os.getenv("ESTER_DATA_ROOT", os.path.join(os.getcwd(), "data"))

    os.environ["ESTER_DATA_ROOT"] = data_root
    os.environ.setdefault("PERSIST_DIR", os.path.join(data_root, "memory"))

    return dict(mounted=mounted, lan_exists=ok_lan, data_root=data_root, drive=_drive_letter(), subdir=_lan_subdir(), unc=_lan_unc())

@_bp.get("/lan/status")
def lan_status():
    info = ensure_data_root_fallback()
    return jsonify(ok=True, **info)

def register(app):
    if _AB == "B":
        ensure_data_root_fallback()
        app.register_blueprint(_bp)
# c=a+b