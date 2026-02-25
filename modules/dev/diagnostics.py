# -*- coding: utf-8 -*-
import json
import os
import time
import platform
from pathlib import Path
from functools import wraps
from flask import Blueprint, Response, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("diagnostics", __name__)

# ---------- helpers ----------

def _json_resp(obj, status=200):
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return Response(data, status=status, mimetype="application/json; charset=utf-8")

def _html_resp(html, status=200):
    return Response(html, status=status, mimetype="text/html; charset=utf-8")

def _data_root_candidates():
    # 1) from the environment (officially)
    env_root = os.getenv("ESTER_DATA_ROOT", "").strip()
    # 2) lokalnaya data/ (sentinel v repozitorii)
    local_data = str(Path("data").absolute())
    # 3) historical Z:ester-date (if installed)
    z_drive = "Z:\\ester-data"
    cands = []
    if env_root:
        # if ESTER_DATA_ROOT == "<PROJECT_ROOT_DRIVE>", the working database is stored in "<PROJECT_ROOT_DRIVE>essier-date"
        # if ESTER_DATA_ROOT == "<PROJECT_ROOT_DRIVE>eeessier-date", this is the database itself
        root = Path(env_root)
        if (root / "memory").exists() or (root / "events").exists() or (root.name.lower() == "ester-data"):
            cands.append(str(root))
        else:
            cands.append(str(root / "ester-data"))
    cands.append(local_data)
    cands.append(z_drive)
    # unikalnye, suschestvuyuschie
    out = []
    seen = set()
    for p in cands:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out

def _is_dev_allowed():
    env = (os.getenv("ESTER_DEV_ALLOW", "") or "").strip().lower()
    if env in ("1", "true", "allow", "yes", "on"):
        return True
    # sentinel file dev.alls in any of the root candidates
    for base in _data_root_candidates():
        try:
            if Path(base, "dev.allow").exists():
                return True
        except Exception:
            pass
    # lokalno v repozitorii (na vsyakiy)
    if Path("data/dev.allow").exists():
        return True
    return False

def _dev_only(fn):
    @wraps(fn)
    def _wrap(*args, **kwargs):
        if not _is_dev_allowed():
            return _json_resp({"ok": False, "error": "dev.disabled"}, status=403)
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            # Never returns to None - only valid JSION
            return _json_resp({"ok": False, "error": "exception", "detail": repr(e)}, status=500)
    return _wrap

# ---------- routes ----------

@bp.route("/_diag/ping", methods=["GET"])
@_dev_only
def diag_ping():
    return _json_resp({
        "ok": True,
        "ts": time.time(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "data_roots": _data_root_candidates(),
        "env": {
            "ESTER_DATA_ROOT": os.getenv("ESTER_DATA_ROOT"),
            "ESTER_JSON_SLOT": os.getenv("ESTER_JSON_SLOT"),
            "ESTER_DEV_ALLOW": os.getenv("ESTER_DEV_ALLOW"),
            "PYTHONIOENCODING": os.getenv("PYTHONIOENCODING"),
        },
    })

@bp.route("/_diag/json", methods=["GET"])
@_dev_only
def diag_json():
    # Mini summary of environment and process
    return _json_resp({
        "ok": True,
        "pid": os.getpid(),
        "time": time.time(),
        "env_keys": sorted([k for k in os.environ.keys() if k.startswith("ESTER_") or k in ("PYTHONIOENCODING",)]),
        "roots": _data_root_candidates(),
    })

@bp.route("/_diag/echo", methods=["POST"])
@_dev_only
def diag_echo():
    payload = request.get_json(silent=True)
    if payload is None:
        raw = request.get_data(cache=False)
        try:
            raw_str = raw.decode("utf-8", "replace")
        except Exception:
            raw_str = str(raw)
        payload = {"_raw": raw_str}
    return _json_resp({
        "ok": True,
        "body": payload,
        "headers": {k: v for k, v in request.headers.items()},
        "args": {k: v for k, v in request.args.items()},
    })

@bp.route("/dev/encoding/probe", methods=["GET"])
@_dev_only
def encoding_probe():
    text = request.args.get("text", "", type=str)
    # Flask already gives a Unicode string; we'll show you the controls
    u = text
    b = u.encode("utf-8", "strict")
    return _json_resp({
        "ok": True,
        "input": u,
        "len": len(u),
        "utf8_hex": b.hex(),
    })

@bp.route("/dev/encoding/sample_html", methods=["GET"])
@_dev_only
def encoding_html():
    html = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>UTF-8 sample</title>
<body>
<h1>Verka UTF-8</h1>
<p>Kirillitsa: Ester umeet govorit po-russki. ✅</p>
<p>Emoji: 😀🔥🚀</p>
</body>
</html>"""
    return _html_resp(html)
