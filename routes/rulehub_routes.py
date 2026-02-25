# -*- coding: utf-8 -*-
"""routes/rulehub_routes.py - REST API dlya nablyudaemosti i upravleniya RuleHub.
  • GET /rulehub/state - counters/last_ts/enabled
  • GET /rulehub/last?limit=N - poslednie sobytiya iz zhurnala
  • POST /rulehub/toggle - {"enabled":1|0}
  • GET /rulehub/config - YAML-tekst
  • POST /rulehub/config - {"yaml":"..."} sokhranit
  • GET /admin/mind/rules - administrativnaya stranitsa UI

Mosty:
- Yavnyy: (Nablyudaemost ↔ Myshlenie) bystryy dostup k schetchikam/zhurnalu i nastroykam.
- Skrytyy #1: (Inzheneriya ↔ Operatsii) toggle i config primenyayutsya bez restartov.
- Skrytyy #2: (Infoteoriya ↔ Kontrol) edinyy HTTP dlya operatorskikh paneley i avtomatov.

Zemnoy abzats (anatomiya/inzheneriya):
This is “pult”: lampochki (state), istoriya (last), tumbler vklyuchit/vyklyuchit (toggle) i yaschik s instructions (config).
Minimum podvizhnykh chastey, determinirovannye otvety, bezopasnaya zapis faylov.

# c=a+b"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_rulehub = Blueprint("rulehub", __name__)

_STATE_DIR = Path(os.getcwd()) / "data" / "rulehub"
_STATE = _STATE_DIR / "state.json"
_LOG = _STATE_DIR / "log.jsonl"
_FLAG = _STATE_DIR / "enable.flag"
_CFG = Path("config") / "rulehub.yaml"


def register(app):  # pragma: no cover
    app.register_blueprint(bp_rulehub)
    # When registering, softly import the patch (if present)
    try:
        import modules.thinking.patch_rulehub  # noqa: F401
    except Exception:
        pass


def init_app(app):  # pragma: no cover
    register(app)


@bp_rulehub.route("/rulehub/state", methods=["GET"])
def rulehub_state():
    st = {"counters": {}, "last_ts": 0}
    if _STATE.exists():
        try:
            st = json.loads(_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    enabled = (os.getenv("RULEHUB_ENABLED", "0") == "1") or _FLAG.exists()
    return jsonify({"ok": True, "enabled": enabled, **st})


@bp_rulehub.route("/rulehub/last", methods=["GET"])
def rulehub_last():
    try:
        limit = int(request.args.get("limit", "100"))
    except Exception:
        limit = 100
    limit = max(1, min(limit, 10000))
    rows: List[Dict[str, Any]] = []
    if _LOG.exists():
        try:
            # Simple hidden along the lines
            lines = _LOG.read_text(encoding="utf-8").splitlines()
            for s in lines[-limit:]:
                try:
                    rows.append(json.loads(s))
                except Exception:
                    continue
        except Exception:
            pass
    return jsonify({"ok": True, "events": rows})


@bp_rulehub.route("/rulehub/toggle", methods=["POST"])
def rulehub_toggle():
    data = request.get_json(force=True, silent=True) or {}
    enabled = bool(int(data.get("enabled", 0)))
    try:
        if enabled:
            _FLAG.parent.mkdir(parents=True, exist_ok=True)
            _FLAG.write_text("1", encoding="utf-8")
        else:
            if _FLAG.exists():
                _FLAG.unlink()
        return jsonify({"ok": True, "enabled": enabled})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_rulehub.route("/rulehub/config", methods=["GET"])
def rulehub_cfg_get():
    txt = ""
    try:
        if _CFG.exists():
            txt = _CFG.read_text(encoding="utf-8")
    except Exception:
        txt = ""
    return jsonify({"ok": True, "yaml": txt})


@bp_rulehub.route("/rulehub/config", methods=["POST"])
def rulehub_cfg_post():
    data = request.get_json(force=True, silent=True) or {}
    yaml_txt = str(data.get("yaml") or "")
    try:
        _CFG.parent.mkdir(parents=True, exist_ok=True)
        _CFG.write_text(yaml_txt, encoding="utf-8")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_rulehub.route("/admin/mind/rules", methods=["GET"])
def admin_ui():
    return render_template("admin_rulehub.html")


__all__ = ["bp_rulehub", "register", "init_app"]
# c=a+b