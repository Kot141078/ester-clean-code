
param(
  [ValidateSet("A","B")] [string]$Mode = "B"  # A=dry-run, B=apply
)
<#
scripts/sitecustomize_relocate.ps1 — peremeschaet sitecustomize.py v KOREN proekta i proveryaet zagruzku.
Mosty:
- Yavnyy: (DevOps↔Rantaym) garantiruet avtopodkhvat sitecustomize Python'om.
- Skrytyy #1: (Diagnostika↔Nadezhnost) proveryaet, chto modul deystvitelno zagruzhen.
- Skrytyy #2: (Discover↔Routy) srazu pokazyvaet nalichie aliasov scan_modules/get_status.
Zemnoy abzats: Python ischet sitecustomize na sys.path (obychno tekuschaya papka proekta). Esli fayl lezhit v scripts\ — on ne gruzitsya. Skript perenosit ego v koren.
c=a+b
#>
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $proj
$src1 = Join-Path $proj "sitecustomize.py"
$dst  = Join-Path $root "sitecustomize.py"

if (Test-Path $src1) {
  if ($Mode -eq "A") { Write-Host "[plan] move $src1 -> $dst" }
  else {
    Move-Item -Force -Path $src1 -Destination $dst
    Write-Host "[ok] moved $src1 -> $dst"
  }
} elseif (Test-Path $dst) {
  Write-Host "[ok] already at $dst"
} else {
  Write-Warning "sitecustomize.py not found in scripts\ or root. Nothing to do."
}

# Checking downloads and discovery aliases
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$code = @'
import sys, importlib, json
loaded = "sitecustomize" in sys.modules
try:
    import modules.app.discover as d
    state = {"has_scan": hasattr(d,"scan"),
             "has_status": hasattr(d,"status"),
             "has_scan_modules": hasattr(d,"scan_modules"),
             "has_get_status": hasattr(d,"get_status")}
except Exception as e:
    state = {"import_error": str(e)}
print(json.dumps({"sitecustomize_loaded": loaded, "discover": state}))
'@
$env:PYTHONIOENCODING="utf-8"
& $py - <<$code
$code
<<$code
# konets
