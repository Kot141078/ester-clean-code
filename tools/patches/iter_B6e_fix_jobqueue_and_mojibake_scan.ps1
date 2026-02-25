param(
  [string]$ProjectRoot = (Get-Location).Path,
  [switch]$FixPassport,
  [switch]$Rollback
)

$ErrorActionPreference = "Stop"

function Write-Ok($m)   { Write-Host ("[OK]  " + $m) -ForegroundColor Green }
function Write-Warn($m) { Write-Host ("[WARN] " + $m) -ForegroundColor Yellow }
function Write-Err($m)  { Write-Host ("[ERR] " + $m) -ForegroundColor Red }

function New-TimeStamp {
  return (Get-Date -Format "yyyyMMdd_HHmmss")
}

function Ensure-Dir($p) {
  if (!(Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null }
}

function Fix-MojibakeUtf8([string]$s) {
  # We restore UTF-8, which was once “read” as sp1251,
  # plus support for K1 control bytes (0x80..0x9F), which often appear in etozhy-mojiwak.
  $cp1251 = [System.Text.Encoding]::GetEncoding(1251)
  $utf8   = [System.Text.Encoding]::UTF8

  $bytes = New-Object System.Collections.Generic.List[byte]
  foreach ($ch in $s.ToCharArray()) {
    $code = [int][char]$ch
    if ($code -ge 0x80 -and $code -le 0x9F) {
      $bytes.Add([byte]$code) | Out-Null
      continue
    }

    $b = $cp1251.GetBytes([string]$ch)
    if ($b.Length -eq 1) {
      $bytes.Add($b[0]) | Out-Null
    } else {
      foreach ($x in $b) { $bytes.Add($x) | Out-Null }
    }
  }

  return $utf8.GetString($bytes.ToArray())
}

function Looks-LikeMojibake([string]$line) {
  # Strong markers of "broken UTF-8" in Russian stocks/text
  # (an ordinary Russian almost never looks like this)
  if ($line -match "rџ") { return $true }    # emoji mojibake
  if ($line -match "vЂ") { return $true }    # tipografika mojibake (—, “ ” i t.p.)
  if ($line -match "R[A-Yaa-ya]") {
    # Be careful: Russian may contain "R", but the series "Р...С..." is typical for Mojiwake
    if ($line -match "R.\S*S") { return $true }
  }
  if ($line -match "vњ") { return $true }    # ✨ i t.p. v mojibake
  return $false
}

function Save-Freeze($py, $dest) {
  & $py -m pip freeze *> $dest
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$venvPy  = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$pass    = Join-Path $ProjectRoot "data\passport\clean_memory.jsonl"
$rbDir   = Join-Path $ProjectRoot "tools\patches\_rollback"
Ensure-Dir $rbDir

if (!(Test-Path $venvPy)) {
  throw "Ne nayden venv python: $venvPy"
}

# --- ROLLBACK ---
if ($Rollback) {
  $cand = Get-ChildItem -Path $rbDir -Filter "clean_memory.jsonl.bak_*" -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending |
          Select-Object -First 1

  if ($cand -and (Test-Path $pass)) {
    Copy-Item -Force $cand.FullName $pass
    Write-Ok ("Rollback passport restored from: " + $cand.FullName)
  } else {
    Write-Warn "Rollback: bekap passport ne nayden (ili net clean_memory.jsonl)."
  }

  $freeze = Get-ChildItem -Path $rbDir -Filter "pip_freeze_before_B6e_*" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

  if ($freeze) {
    Write-Ok ("Rollback hint: u tebya sokhranen freeze: " + $freeze.FullName)
    Write-Warn "Esli nuzhno otkatyvat pakety — delay vruchnuyu po freeze (pip install -r), ya tut avtomatom ne lezu."
  }

  Write-Ok "Done (rollback)."
  exit 0
}

# --- 1) FIX VENV: JobQueue ---
$ts = New-TimeStamp
$freezePath = Join-Path $rbDir ("pip_freeze_before_B6e_" + $ts + ".txt")
Save-Freeze $venvPy $freezePath
Write-Ok ("Saved freeze: " + $freezePath)

Write-Ok "Installing PTB JobQueue extra (so volition/heartbeat works in venv)..."
# Rigidly fixes the same branch that you already have: 11.21.1
& $venvPy -m pip install -U "python-telegram-bot[job-queue]==21.11.1" | Out-Host

# Mini-check that the fuck_queue actually appeared
$probe = @"
from telegram.ext import ApplicationBuilder
app = ApplicationBuilder().token("0:0").build()
print("job_queue_enabled=", bool(app.job_queue))
"@
& $venvPy -c $probe | Out-Host

# --- 2) SCAN FOR MOJIBAKE ---
Write-Ok "Scanning project for mojibake markers..."
$targets = @(
  (Join-Path $ProjectRoot "run_ester_fixed.py"),
  (Join-Path $ProjectRoot "data\passport\clean_memory.jsonl"),
  (Join-Path $ProjectRoot "data\passport\*.jsonl"),
  (Join-Path $ProjectRoot "logs\*.log"),
  (Join-Path $ProjectRoot "*.log")
)

$markers = @("rџ","vЂ","vњ","R—R","RЈS") # bystrye signaly
$foundAny = $false

foreach ($t in $targets) {
  $items = Get-ChildItem -Path $t -ErrorAction SilentlyContinue
  foreach ($it in $items) {
    if ($it.PSIsContainer) { continue }
    $hits = Select-String -Path $it.FullName -SimpleMatch -Pattern $markers -ErrorAction SilentlyContinue
    if ($hits) {
      $foundAny = $true
      Write-Warn ("MOJIBAKE? " + $it.FullName)
      $hits | Select-Object -First 15 | ForEach-Object {
        Write-Host ("  L" + $_.LineNumber + ": " + $_.Line)
      }
    }
  }
}

if (-not $foundAny) {
  Write-Ok "No mojibake markers found in scanned targets."
}

# --- 3) OPTIONAL: FIX passport JSONL ---
if ($FixPassport) {
  if (!(Test-Path $pass)) {
    Write-Warn ("Passport not found: " + $pass)
  } else {
    $bak = Join-Path $rbDir ("clean_memory.jsonl.bak_" + $ts)
    Copy-Item -Force $pass $bak
    Write-Ok ("Backup passport: " + $bak)

    # Read/write like UTF-8 without BOT
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $lines = [System.IO.File]::ReadAllLines($pass, $utf8NoBom)

    $changed = 0
    for ($i=0; $i -lt $lines.Length; $i++) {
      $ln = $lines[$i]
      if (Looks-LikeMojibake $ln) {
        $fx = Fix-MojibakeUtf8 $ln

        # The “A/B with auto-rollback” principle: we accept a fix only if it has become “cleaner”
        $badBefore = Looks-LikeMojibake $ln
        $badAfter  = Looks-LikeMojibake $fx

        if ($badBefore -and (-not $badAfter) -and ($fx -notmatch [char]0xFFFD)) {
          $lines[$i] = $fx
          $changed++
        }
      }
    }

    if ($changed -gt 0) {
      [System.IO.File]::WriteAllLines($pass, $lines, $utf8NoBom)
      Write-Ok ("Passport fixed lines: " + $changed)
    } else {
      Write-Ok "Passport: nothing safe to fix (or already clean)."
    }
  }
}

Write-Ok "Done."
Write-Host ""
Write-Host "Next run (venv):" -ForegroundColor Cyan
Write-Host ("  cd " + $ProjectRoot) -ForegroundColor Cyan
Write-Host "  $env:PORT='8090'" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python.exe run_ester_fixed.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "If console shows mojibake, run once per session:" -ForegroundColor Cyan
Write-Host "  chcp 65001" -ForegroundColor Cyan
Write-Host "  $env:PYTHONUTF8='1'" -ForegroundColor Cyan
Write-Host "  $env:PYTHONIOENCODING='utf-8'" -ForegroundColor Cyan
