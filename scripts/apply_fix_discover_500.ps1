
<# 
scripts/apply_fix_discover_500.ps1 — garantirovannaya perezapis trekh faylov v proekte.
Mosty:
- Yavnyy: (DevOps ↔ Kod) zapisyvaet ispravlennye fayly pryamo v nuzhnye puti.
- Skrytyy #1: (Kontrol ↔ Nadezhnost) proveryaet, chto papki suschestvuyut; sozdaet ikh pri neobkhodimosti.
- Skrytyy #2: (A/B) supports -Mode A (only show paths), -Mode B (write).

Zemnoy abzats:
Inogda «polozhil poverkh» ne srabatyvaet. Etot skript sam sozdaet/perezapisyvaet
`routes/app_discover_routes.py`, `routes/favicon_routes.py`, `tools/verify_routes.py`.
c=a+b
#>
param(
  [ValidateSet("A","B")] [string]$Mode="B"
)

function Write-FileUtf8 {
  param([string]$Path, [string]$Content)
  $dir = Split-Path $Path
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$proj = Split-Path -Parent $root  # assumes location of scriptc/ in the project root

$files = @{
  "routes\app_discover_routes.py" = @'
# -*- coding: utf-8 -*-
from __future__ import annotations
import importlib, os
from typing import Any, Dict, List, Tuple
from flask import Blueprint, jsonify, request, current_app

bp = Blueprint("app_discover_routes", __name__, url_prefix="")

def _collect_routes(app) -> Dict[str, Any]:
    out = []
    try:
        rules = list(app.url_map.iter_rules())
        for r in rules:
            methods = sorted(m for m in r.methods if m not in ("HEAD","OPTIONS"))
            out.append({"path": str(r.rule), "methods": methods, "endpoint": r.endpoint})
        out = sorted(out, key=lambda x: x["path"])
        return {"count": len(out), "items": out[:500]}
    except Exception as e:
        return {"error": str(e), "count": 0, "items": []}

def _safe_direct_register(app, dotted: str) -> Tuple[bool, str]:
    try:
        mod = importlib.import_module(dotted)
    except Exception as e:
        return False, f"import:{e}"
    try:
        if hasattr(mod, "register") and callable(getattr(mod, "register")):
            mod.register(app)
        elif hasattr(mod, "bp"):
            app.register_blueprint(getattr(mod, "bp"))
        return True, "ok"
    except Exception as e:
        return False, f"register:{e}"

@bp.route("/app/discover/scan", methods=["GET"])
def api_scan():
    try:
        r = _collect_routes(current_app)
        return jsonify({"ok": True, "routes": r})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.route("/app/discover/status", methods=["GET"])
def api_status():
    try:
        try:
            from modules.thinking.action_registry import list_registered as _alist  # type: ignore
            ac = len(_alist())
        except Exception:
            ac = 0
        routes = _collect_routes(current_app)
        return jsonify({"ok": True, "routes": routes.get("count", 0), "actions": ac})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.route("/app/discover/register", methods=["POST"])
def api_register():
    d = request.get_json(force=True, silent=True) or {}
    mods = list(d.get("modules") or [])
    done: List[str] = []
    errs: Dict[str, str] = {}
    for m in mods:
        ok, note = _safe_direct_register(current_app, str(m))
        (done if ok else errs).__setitem__(m, note) if not ok else done.append(m)
    return jsonify({"ok": True, "registered": done, "errors": errs})

@bp.route("/debug/actions/reload", methods=["POST"])
def debug_actions_reload():
    try:
        from actions_discovery import discover_actions  # type: ignore
    except Exception:
        discover_actions = None  # type: ignore
    try:
        if discover_actions is not None:
            reg = discover_actions(current_app)  # type: ignore
            count = len(reg) if reg is not None else 0
        else:
            try:
                from modules.thinking.action_registry import list_registered as _alist  # type: ignore
                count = len(_alist())
            except Exception:
                count = 0
        return jsonify({"ok": True, "registered": int(count)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def register(app):
    app.register_blueprint(bp)
'@

  "routes\favicon_routes.py" = @'
# -*- coding: utf-8 -*-
from __future__ import annotations
from io import BytesIO
from flask import Blueprint, send_file, Response
bp = Blueprint("favicon_routes", __name__)

@bp.route("/favicon.ico", methods=["GET"])
def favicon():
    try:
        data_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAn8B9x1x7iAAAAAASUVORK5CYII="
        import base64
        data = BytesIO(base64.b64decode(data_b64))
        data.seek(0)
        return send_file(data, mimetype="image/png", as_attachment=False, download_name="favicon.png")
    except Exception:
        return Response(status=204)

def register(app):
    app.register_blueprint(bp)
'@

  "tools\verify_routes.py" = @'
# -*- coding: utf-8 -*-
from __future__ import annotations
import json, os, sys, urllib.request, urllib.error
def _ep(path: str) -> str:
    host = os.getenv("HOST", "127.0.0.1"); port = os.getenv("PORT", "8137")
    return f"http://{host}:{port}{path}"
def _req(method:str, path:str, data:dict|None=None):
    body = None
    if data is not None: body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(_ep(path), method=method, data=body, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.getcode(), json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode("utf-8"))
        except: return e.code, {"ok": False, "error": str(e)}
    except Exception as e:
        return 0, {"ok": False, "error": str(e)}
def main()->int:
    for m,p,pl in (("GET","/debug/doctor?details=1",None),
                   ("GET","/app/discover/scan",None),
                   ("POST","/debug/actions/reload",{})):
        code, doc = _req(m,p,pl); print(p, code, json.dumps(doc, ensure_ascii=False)[:400])
    code, doc = _req("POST","/debug/actions/reload",{})
    return 0 if (code==200 and isinstance(doc,dict) and doc.get("ok")) else 1
if __name__=="__main__": sys.exit(main())
'@
}

if ($Mode -eq "A") {
  $files.Keys | ForEach-Object { Write-Host "[plan] $($_)" }
  exit 0
}

foreach ($rel in $files.Keys) {
  $target = Join-Path $proj $rel
  Write-Host "[write] $target"
  Write-FileUtf8 -Path $target -Content $files[$rel]
}
Write-Host "[ok] all files written."
