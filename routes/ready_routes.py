# -*- coding: utf-8 -*-
from __future__ import annotations
"""
routes/ready_routes.py — /live i /ready (zhivuchest i gotovnost servisa).

/live  → vsegda 200, esli protsess otvechaet.
/ready → 200, kogda kritichnye zavisimosti v poryadke; inache 503.

MOSTY:
- Yavnyy: Observability ↔ Runtime — odno mesto dlya liveness/readiness.
- Skrytyy #1: ENV ↔ Povedenie — ESTER_BACKUP_MAX_AGE_H/… upravlyayut proverkami bez pravki koda.
- Skrytyy #2: Backup ↔ Khranilische — chitaem mtime fayla «poslednego uspeshnogo bekapa» kak SLI.

ZEMNOY ABZATs (inzheneriya):
Bag «UnboundLocalError: local variable 'os' referenced before assignment» voznik iz-za
lokalnogo `import os` VNUTRI funktsii, gde `os` ispolzuetsya DO importa. V Python eto
prevraschaet `os` v lokalnuyu peremennuyu na vsyu funktsiyu. Fiks — importiruem os/time na
urovne modulya i ne pereopredelyaem ikh v funktsiyakh. Takzhe garantiruem vozvrat otveta iz /ready.
# c=a+b
"""
import os
import time
import base64
from typing import Tuple

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import yaml  # type: ignore
    _HAVE_YAML = True
except Exception:
    yaml = None  # type: ignore
    _HAVE_YAML = False

bp_ready = Blueprint("ready", __name__)


@bp_ready.get("/live")
def live():
    return jsonify(ok=True, status="live"), 200


# --- checks ---------------------------------------------------------------

def _check_secrets() -> Tuple[bool, str]:
    required = ["JWT_SECRET"]
    missing = [k for k in required if not (os.getenv(k) or "").strip()]
    if missing:
        return False, "missing: " + ",".join(missing)

    emk = (os.getenv("ENCRYPTION_MASTER_KEY_BASE64") or "").strip()
    if emk:
        try:
            base64.urlsafe_b64decode(emk.encode("utf-8"))
        except Exception:
            return False, "ENCRYPTION_MASTER_KEY_BASE64 invalid"
    return True, "ok"


def _check_backup_freshness() -> Tuple[bool, str]:
    """
    Proveryaem, chto time_since(last_success) <= ESTER_BACKUP_MAX_AGE_H.
    Esli peremennaya ne zadana ili <=0 — proverku propuskaem.
    """
    try:
        max_h = int((os.getenv("ESTER_BACKUP_MAX_AGE_H") or "0").strip() or "0")
    except Exception:
        max_h = 0

    if max_h <= 0:
        return True, "skip"

    ts_file = (os.getenv("ESTER_BACKUP_LAST_TS_FILE") or "artifacts/backup/last_success.ts").strip()
    try:
        if not os.path.exists(ts_file):
            return False, f"no {ts_file}"
        age_h = (time.time() - os.path.getmtime(ts_file)) / 3600.0
        return (age_h <= max_h), f"age_h={age_h:.2f} (max {max_h})"
    except Exception as e:
        return False, f"err: {e}"


def _check_feature_flags() -> Tuple[bool, str]:
    """
    Zagruzhaem YAML pri nalichii PyYAML; esli fayla net — propuskaem, esli YAML bityy — oshibka.
    """
    path = (os.getenv("ESTER_FEATURE_FLAGS") or "config/feature_flags.yaml").strip()
    if not os.path.exists(path):
        return True, "skip"
    if not _HAVE_YAML:
        return True, "skip(yaml-unavailable)"
    try:
        with open(path, "r", encoding="utf-8") as f:
            yaml.safe_load(f)  # type: ignore
        return True, "ok"
    except Exception as e:
        return False, f"err: {e}"


@bp_ready.get("/ready")
def ready():
    checks = {
        "secrets": _check_secrets(),
        "backup_freshness": _check_backup_freshness(),
        "feature_flags": _check_feature_flags(),
    }
    ok = all(v[0] for v in checks.values())
    payload = {k: {"ok": v[0], "info": v[1]} for k, v in checks.items()}
    payload["ok"] = ok
    return jsonify(payload), (200 if ok else 503)


def register(app):
    app.register_blueprint(bp_ready)
    return app