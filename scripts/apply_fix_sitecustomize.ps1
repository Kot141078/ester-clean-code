
<# scripts\apply_fix_sitecustomize.ps1 — kladet sitecustomize.py v koren proekta
Mosty: Yavnyy (DevOps↔Kod), Skrytye (A/V; Nadezhnost↔Kontrol).
Zemnoy abzats: odin fayl fiksit nesovmestimost imen i 500 na discover/doctor. c=a+b #>
param([ValidateSet("A","B")] [string]$Mode="B")
function Write-FileUtf8 { param([string]$Path,[string]$Content)
  $dir=Split-Path $Path; if(-not(Test-Path $dir)){New-Item -ItemType Directory -Force -Path $dir|Out-Null}
  $utf8=New-Object System.Text.UTF8Encoding($false); [System.IO.File]::WriteAllText($Path,$Content,$utf8)
}
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $proj "sitecustomize.py"
if($Mode -eq "A"){ Write-Host "[plan] -> $target"; exit 0 }
$payload = @'

# -*- coding: utf-8 -*-
"""
sitecustomize.py — sovmestimost rantayma dlya Ester.
Mosty:
- Yavnyy: (Staryy discover ↔ Novye routy) dobavlyaet aliasy scan_modules/get_status v modules.app.discover.
- Skrytyy #1: (DevOps ↔ Nadezhnost) prevraschaet "jupytext(...)" v alias na flask.jsonify(...).
- Skrytyy #2: (ENV ↔ Adaptery) LMSTUDIO_BASE_URL ← LMSTUDIO_URL, esli ne zadan.
Zemnoy abzats: Python avtomaticheski podkhvatyvaet sitecustomize pri starte. My «podstilaem solomku»,
chtoby dazhe nesovpadayuschie imena funktsiy ne ronyali veb-interfeys. c=a+b
"""
from __future__ import annotations

# 1) jupytext(...) → flask.jsonify(...), esli gde-to staryy vyzov
try:
    import builtins
    def jupytext(payload=None, *args, **kwargs):  # type: ignore
        try:
            from flask import jsonify, Response
            try:
                return jsonify(payload)
            except Exception:
                import json as _json
                return Response(_json.dumps(payload or {}), mimetype="application/json")
        except Exception:
            return payload
    builtins.jupytext = jupytext  # type: ignore[attr-defined]
except Exception:
    pass

# 2) ENV most
import os as _os
if not _os.getenv("LMSTUDIO_BASE_URL") and _os.getenv("LMSTUDIO_URL"):
    _os.environ["LMSTUDIO_BASE_URL"] = _os.environ["LMSTUDIO_URL"]

# 3) Aliasy dlya modules.app.discover: scan_modules → scan, get_status → status
def _patch_discover_aliases() -> None:
    try:
        import importlib
        m = importlib.import_module("modules.app.discover")
        # esli v module net nuzhnykh imen — zavedem
        if not hasattr(m, "scan_modules") and hasattr(m, "scan"):
            setattr(m, "scan_modules", getattr(m, "scan"))
        if not hasattr(m, "get_status") and hasattr(m, "status"):
            setattr(m, "get_status", getattr(m, "status"))
    except Exception:
        # myagko — nichego strashnogo, esli modul poyavitsya pozzhe
        pass

_patch_discover_aliases()

'@
Write-FileUtf8 -Path $target -Content $payload
Write-Host "[ok] wrote $target"
