param(
  [switch]$Rollback,
  [switch]$FixPassport
)

$ErrorActionPreference = "Stop"

function Write-Ok($m){ Write-Host ("[OK]  " + $m) -ForegroundColor Green }
function Write-Warn($m){ Write-Host ("[WARN] " + $m) -ForegroundColor Yellow }
function Write-Err($m){ Write-Host ("[ERR] " + $m) -ForegroundColor Red }

function Get-ProjectRoot {
  $cwd = (Get-Location).Path
  if (Test-Path (Join-Path $cwd "run_ester_fixed.py")) { return $cwd }

  $here = Split-Path -Parent $MyInvocation.MyCommand.Path
  $cand = (Resolve-Path (Join-Path $here "..\..")).Path
  if (Test-Path (Join-Path $cand "run_ester_fixed.py")) { return $cand }

  throw "Project root not found. Run from D:\ester-project or place script under tools\patches\."
}

function Latest-File($dir, $filter){
  if (!(Test-Path $dir)) { return $null }
  $f = Get-ChildItem -Path $dir -Filter $filter -File -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
  return $f
}

function Contains-MojibakeLikely([string]$s){
  if ([string]::IsNullOrEmpty($s)) { return $false }
  if ($s.Length -lt 20) { return $false }

  # Heuristic: high density of Cyrillic capital ER/ES (U+0420/U+0421) in long lines
  $cR = [char]0x0420
  $cS = [char]0x0421
  $count = 0
  for ($i=0; $i -lt $s.Length; $i++){
    $ch = $s[$i]
    if ($ch -eq $cR -or $ch -eq $cS) { $count++ }
  }
  $ratio = [double]$count / [double]$s.Length
  if ($ratio -ge 0.12) { return $true }

  # Classic UTF-8 bytes shown as Win-1252/Latin-1 letters
  if ($s.IndexOf([char]0x00F0) -ge 0) { return $true } # ð
  if ($s.IndexOf([char]0x00E2) -ge 0) { return $true } # â
  if ($s.IndexOf([char]0x00D0) -ge 0) { return $true } # Ð
  if ($s.IndexOf([char]0x00D1) -ge 0) { return $true } # Ñ

  return $false
}

function Try-Fix-Utf8FromCp1251([string]$s){
  try {
    $cp = [System.Text.Encoding]::GetEncoding(1251)
    $u8 = New-Object System.Text.UTF8Encoding($false)
    $bytes = $cp.GetBytes($s)
    return $u8.GetString($bytes)
  } catch {
    return $s
  }
}

function Read-Utf8Lines([string]$path){
  $u8 = New-Object System.Text.UTF8Encoding($false)
  return [System.IO.File]::ReadLines($path, $u8)
}

function Scan-Globs($globs, [int]$maxHitsPerFile){
  Write-Ok "Mojibake scan (UTF-8 read + heuristic) ..."
  foreach ($g in $globs){
    $dir  = Split-Path -Parent $g
    $leaf = Split-Path -Leaf $g
    if (!(Test-Path $dir)) { continue }

    $files = Get-ChildItem -Path $dir -Filter $leaf -File -ErrorAction SilentlyContinue
    foreach ($f in $files){
      $hits = 0
      $ln = 0
      try {
        foreach ($line in (Read-Utf8Lines $f.FullName)){
          $ln++
          if ($hits -ge $maxHitsPerFile) { break }
          if (Contains-MojibakeLikely $line){
            $hits++
            $snipLen = [Math]::Min(140, $line.Length)
            $snip = $line.Substring(0, $snipLen)
            Write-Warn ("HIT {0}:{1}  {2}" -f $f.FullName, $ln, $snip)
          }
        }
      } catch {
        # ignore locked/binary
      }
    }
  }
}

# ---------------- main ----------------
$proj = Get-ProjectRoot
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$rbDir = Join-Path $proj "tools\patches\_rollback"
New-Item -ItemType Directory -Force -Path $rbDir | Out-Null

$venvPy = Join-Path $proj ".venv\Scripts\python.exe"
if (!(Test-Path $venvPy)) { throw "Missing venv python: $venvPy" }

Write-Ok ("ProjectRoot: " + $proj)

if ($Rollback){
  Write-Warn "ROLLBACK requested."

  $freeze = Latest-File $rbDir "pip_freeze_before_B6e2_*.txt"
  if ($freeze -eq $null) { throw "No freeze file found in $rbDir (pip_freeze_before_B6e2_*.txt)" }
  Write-Ok ("Using freeze: " + $freeze.FullName)
  & $venvPy -m pip install -r $freeze.FullName | Out-Host

  $runner = Join-Path $proj "tools\run_ester_utf8.ps1"
  $runnerBak = Latest-File $rbDir "run_ester_utf8.ps1.bak_B6e2_*"
  if ($runnerBak -ne $null){
    Copy-Item $runnerBak.FullName $runner -Force
    Write-Ok ("Restored runner from: " + $runnerBak.FullName)
  } elseif (Test-Path $runner){
    Remove-Item $runner -Force
    Write-Ok "Removed runner (no backup existed)."
  }

  $pass = Join-Path $proj "data\passport\clean_memory.jsonl"
  $passBak = Latest-File $rbDir "clean_memory.jsonl.bak_B6e2_*"
  if ($passBak -ne $null -and (Test-Path $pass)){
    Copy-Item $passBak.FullName $pass -Force
    Write-Ok ("Restored passport from: " + $passBak.FullName)
  }

  Write-Ok "Rollback done."
  exit 0
}

# Save freeze for rollback
$freezePath = Join-Path $rbDir ("pip_freeze_before_B6e2_" + $ts + ".txt")
& $venvPy -m pip freeze | Out-File -FilePath $freezePath -Encoding ASCII
Write-Ok ("Saved freeze: " + $freezePath)

# Install JobQueue extras for PTB
Write-Ok "Installing python-telegram-bot[job-queue] into venv ..."
& $venvPy -m pip install -U "python-telegram-bot[job-queue]" | Out-Host

# Quick probe: show versions
Write-Ok "Probing installed versions (venv) ..."
& $venvPy -c "import sys; print('python=',sys.version.split()[0]); import telegram; print('ptb=',getattr(telegram,'__version__','?')); import apscheduler; print('apscheduler=',getattr(apscheduler,'__version__','?'))" | Out-Host

# Write UTF-8 runner (ASCII file content)
$runner = Join-Path $proj "tools\run_ester_utf8.ps1"
if (Test-Path $runner){
  $bak = Join-Path $rbDir ("run_ester_utf8.ps1.bak_B6e2_" + $ts)
  Copy-Item $runner $bak -Force
  Write-Ok ("Backup runner: " + $bak)
}

$runnerLines = @(
'$ErrorActionPreference = "Stop"'
'$proj = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent'
'Set-Location $proj'
'try { chcp 65001 | Out-Null } catch {}'
'[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)'
'$env:PYTHONUTF8 = "1"'
'$env:PYTHONIOENCODING = "utf-8"'
'if (-not $env:PORT) { $env:PORT = "8090" }'
'$py = Join-Path $proj ".venv\Scripts\python.exe"'
'if (!(Test-Path $py)) { $py = "python.exe" }'
'& $py (Join-Path $proj "run_ester_fixed.py")'
)
$runnerLines | Set-Content -Path $runner -Encoding ASCII
Write-Ok ("Wrote UTF-8 runner: " + $runner)

# Scan likely problem files
$globs = @(
  (Join-Path $proj "data\passport\*.jsonl"),
  (Join-Path $proj "logs\*.log"),
  (Join-Path $proj "run_ester_fixed.py"),
  (Join-Path $proj "modules\*.py"),
  (Join-Path $proj "bridges\*.py")
)
Scan-Globs $globs 3

# Optional: attempt to fix passport lines (only if explicitly requested)
if ($FixPassport){
  $pass = Join-Path $proj "data\passport\clean_memory.jsonl"
  if (Test-Path $pass){
    $bak = Join-Path $rbDir ("clean_memory.jsonl.bak_B6e2_" + $ts)
    Copy-Item $pass $bak -Force
    Write-Ok ("Backup passport: " + $bak)

    $u8 = New-Object System.Text.UTF8Encoding($false)
    $out = New-Object System.Collections.Generic.List[string]
    $changed = 0

    foreach ($line in (Read-Utf8Lines $pass)){
      $cur = $line
      if (Contains-MojibakeLikely $cur){
        $fixed = Try-Fix-Utf8FromCp1251 $cur
        if ($fixed -ne $cur){
          $cur = $fixed
          $changed++
        }
      }
      $out.Add($cur)
    }

    if ($changed -gt 0){
      [System.IO.File]::WriteAllLines($pass, $out, $u8)
      Write-Ok ("Passport fixed lines: " + $changed)
    } else {
      Write-Ok "Passport looks OK (no changes)."
    }
  } else {
    Write-Warn ("Passport not found: " + $pass)
  }
}

Write-Ok "B6e2 applied."

Write-Host "Next:" -ForegroundColor Cyan
Write-Host ("  cd " + $proj) -ForegroundColor Cyan
Write-Host "  `$env:PORT='8090'" -ForegroundColor Cyan
Write-Host "  .\tools\run_ester_utf8.ps1" -ForegroundColor Cyan

# Bridges + Earth (ASCII-only):
# Explicit bridge: c=a+b -> human intent (a) + rollback procedure/tooling (b) => stable operation (c).
# Hidden bridges: Ashby (variety via fallback paths), Cover&Thomas (robust channel via encoding control),
# Gray's Anatomy (do not fuse tissues wrongly: encoding boundaries as clean sutures).
# Earth: Like a rack power adapter: if plug standard (encoding) mismatches socket (console),
# the signal sparks into gibberish; fix the adapter first, then debug the device.
