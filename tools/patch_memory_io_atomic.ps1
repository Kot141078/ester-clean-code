param([switch]$DryRun)

$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){   Write-Host "[OK]  $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err($m){  Write-Host "[ERR]  $m" -ForegroundColor Red }

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root     = Split-Path -Parent $toolsDir

$target = Join-Path $root "modules\memory\io.py"
if(-not (Test-Path $target)){ throw "Not found: $target" }

$stamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$bak   = "$target.bak_$stamp"

Copy-Item $target $bak -Force
Info "Backup: $bak"

$new = @'
# -*- coding: utf-8 -*-
"""
modules/memory/io.py — vvod/vyvod pamyati.

Funktsii:
- save_snapshot(path, data)
- load_snapshot(path)

Fiks:
- atomarnaya zapis NA TOY ZhE FS: temp-fayl sozdaetsya v direktorii naznacheniya i zamenyaetsya cherez os.replace()
- pri bitom JSON: fayl karantiniruetsya (*.corrupt_YYYYMMDD_HHMMSS) i vozvraschaetsya {}

# c=a+b
"""
from typing import Dict, Any
import os
import json
import tempfile
import time


def save_snapshot(path: str, data: Dict[str, Any]) -> None:
    """
    Atomic save on the same filesystem:
    - create temp file in target directory
    - write
    - os.replace() to final path (atomic on same FS)
    """
    dir_ = os.path.dirname(path) or "."
    os.makedirs(dir_, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_mem_", suffix=".json", dir=dir_, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # compact: writes faster, less chance of catching a half-broken file when killing a process externally
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def load_snapshot(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        # quarantine corrupt file
        stamp = time.strftime("%Y%m%d_%H%M%S")
        bad = f"{path}.corrupt_{stamp}"
        try:
            os.replace(path, bad)
        except Exception:
            try:
                os.rename(path, bad)
            except Exception:
                pass
        return {}
'@

if($DryRun){
  Info "DryRun: not writing."
  exit 0
}

Set-Content -Path $target -Value $new -Encoding UTF8
Ok "Written: $target"

Info "py_compile..."
& python -m py_compile $target
if($LASTEXITCODE -ne 0){
  Err "py_compile FAILED -> rollback"
  Copy-Item $bak $target -Force
  exit 1
}

Ok "py_compile OK"
Info "Done."