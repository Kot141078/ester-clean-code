#requires -Version 5.1
<#
Ester patch B5b: fix unicodeescape SyntaxError in run_ester_fixed.py docstring

Explicit bridge (c=a+b):
- a: tekst/dokstring v iskhodnike
- b: protsedura ekranirovaniya (\\u vmesto \u) + smoke-compile
- c: fayl snova parsitsya, Telegram-khendler ne valit ves tsikl

Hidden bridges:
- Enderton (formalnye yazyki): literaly — eto “alfavit”, ekranirovanie sokhranyaet grammatiku
- Cover&Thomas (kanal): ubiraem “shum dekodera” (\u-parser), povyshaem nadezhnost peredachi
- Gray’s Anatomy (provodimost): kak mielin — pravilnaya izolyatsiya backslash, chtoby impuls ne “korotnul”

Earth (inzheneriya/anatomiya):
Eto klassicheskaya “proboina izolyatsii”: odin golyy \u v dokstringe — i vsya liniya pitaniya (parser) padaet.
My ne trogaem logiku, tolko izolyatsiyu; zatem delaem test na “prozvon” (py_compile).
#>

param(
  [switch]$Rollback,
  [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$proj = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$run  = Join-Path $proj "run_ester_fixed.py"

if (!(Test-Path $run)) { throw "Ne nayden: $run" }

# rollback: vosstanovit samyy svezhiy backup
if ($Rollback) {
  $latest = Get-ChildItem -Path ($run + ".bak_*") -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
  if (!$latest) { throw "Ne nayden backup: $($run).bak_*" }
  Copy-Item $latest.FullName $run -Force
  Write-Host "[OK] Rolled back to $($latest.FullName)"
  exit 0
}

$ts  = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$run.bak_$ts"
Copy-Item $run $bak -Force
Write-Host "Backup: $bak"

# Read/Write UTF-8 no BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$content   = [System.IO.File]::ReadAllText($run, $utf8NoBom)

$old = 'via \uXXXX escapes'
$new = 'via \\uXXXX escapes'

if ($content.Contains($old)) {
  $content = $content.Replace($old, $new)
  Write-Host "[patch] docstring: '$old' -> '$new'"
} else {
  Write-Host "[warn] exact pattern not found: $old"
  Write-Host "       If still failing, search manually for a lone '\u' in triple-quoted strings."
}

[System.IO.File]::WriteAllText($run, $content, $utf8NoBom)

# Choose python for smoke compile
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
  $venvPy = Join-Path $proj ".venv\Scripts\python.exe"
  if (Test-Path $venvPy) { $PythonExe = $venvPy } else { $PythonExe = "python" }
}

Write-Host "[smoke] py_compile using: $PythonExe"
$py = "import py_compile; py_compile.compile(r'$run', doraise=True); print('OK: run_ester_fixed.py parses')"
& $PythonExe -c $py

if ($LASTEXITCODE -ne 0) {
  Write-Host "[FAIL] parse test failed; restoring backup..."
  Copy-Item $bak $run -Force
  throw "Patch failed; restored backup: $bak"
}

Write-Host "[OK] B5b applied."
Write-Host "Run Ester with the Python that has torch+deps:"
Write-Host "  .\.venv\Scripts\python.exe run_ester_fixed.py   (esli torch ustanovlen v venv)"
Write-Host "  C:\Python310\python.exe run_ester_fixed.py     (esli vse pakety tam)"
