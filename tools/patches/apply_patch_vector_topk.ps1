param(
  [string]$Path = ".\run_ester_fixed.py",
  [switch]$FromBackup,
  [string]$BackupPath = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function New-BackupPath([string]$p) {
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  return ($p + ".bak_" + $ts)
}

function Backup-File([string]$p) {
  if (!(Test-Path -LiteralPath $p)) { throw "File not found: $p" }
  $bak = New-BackupPath $p
  Copy-Item -LiteralPath $p -Destination $bak -Force
  Write-Host ("Backup created: " + $bak)
  return $bak
}

function Restore-File([string]$src, [string]$dst) {
  if (!(Test-Path -LiteralPath $src)) { throw "Backup not found: $src" }
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Host ("Rollback OK -> " + $dst)
}

function Find-LineIndex([string[]]$lines, [string]$pattern, [int]$startIdx = 0) {
  for ($i=$startIdx; $i -lt $lines.Length; $i++) {
    if ($lines[$i] -match $pattern) { return $i }
  }
  return -1
}

function Insert-AfterLine([ref]$linesRef, [int]$idx, [string[]]$toInsert) {
  $lines = $linesRef.Value
  $before = @()
  if ($idx -ge 0) { $before = $lines[0..$idx] }
  $after = @()
  if ($idx + 1 -le $lines.Length - 1) { $after = $lines[($idx+1)..($lines.Length-1)] }
  $linesRef.Value = @($before + $toInsert + $after)
}

# --- BRIDGES (explicit/hidden) + EARTH paragraph (kept ASCII to avoid PS5 encoding traps) ---
# EXPLICIT: c=a+b -> human sets bounds (topK), code enforces them (clamp + rollback).
# HIDDEN: Ashby requisite variety -> more candidates improves stability of recall.
# HIDDEN: Cover&Thomas channel capacity -> clamp prevents prompt-bandwidth overload.
# EARTH: Like a pressure regulator valve: too low flow starves the system, too high floods it.

if ($FromBackup) {
  if ([string]::IsNullOrWhiteSpace($BackupPath)) { throw "Use -BackupPath when -FromBackup is set." }
  Restore-File -src $BackupPath -dst $Path
  exit 0
}

$bakPath = Backup-File $Path

try {
  $lines = Get-Content -LiteralPath $Path -Encoding UTF8

  # 1) Insert VECTOR_TOPK + _clamp_topk helper (once), right after DREAM_FALLBACK_ADMIN_CHAT
  $hasTopk = ($lines | Select-String -SimpleMatch "VECTOR_TOPK_DEFAULT" -Quiet)
  if (-not $hasTopk) {
    $idxAnchor = Find-LineIndex -lines $lines -pattern '^\s*DREAM_FALLBACK_ADMIN_CHAT\s*=' -startIdx 0
    if ($idxAnchor -lt 0) { throw "ANCHOR_NOT_FOUND: DREAM_FALLBACK_ADMIN_CHAT" }

    $insert = @(
      "",
      "# --- VECTOR TOPK (chroma recall) ---",
      "VECTOR_TOPK_DEFAULT = int(os.getenv(""VECTOR_TOPK_DEFAULT"", ""30""))",
      "VECTOR_TOPK_MIN = int(os.getenv(""VECTOR_TOPK_MIN"", ""20""))",
      "VECTOR_TOPK_MAX = int(os.getenv(""VECTOR_TOPK_MAX"", ""50""))",
      "",
      "def _clamp_topk(v: int) -> int:",
      "    try:",
      "        v = int(v)",
      "    except Exception:",
      "        v = VECTOR_TOPK_DEFAULT",
      "    if v < VECTOR_TOPK_MIN:",
      "        v = VECTOR_TOPK_MIN",
      "    if v > VECTOR_TOPK_MAX:",
      "        v = VECTOR_TOPK_MAX",
      "    return v",
      ""
    )

    $refLines = [ref]$lines
    Insert-AfterLine -linesRef $refLines -idx $idxAnchor -toInsert $insert
    $lines = $refLines.Value
    Write-Host "Inserted VECTOR_TOPK + _clamp_topk."
  } else {
    Write-Host "VECTOR_TOPK already present -> skipping helper insert."
  }

  # 2) Patch recall() only
  $idxRecall = Find-LineIndex -lines $lines -pattern '^\s{4}def\s+recall\s*\(' -startIdx 0
  if ($idxRecall -lt 0) { throw "Could not find: def recall(" }

  $idxEnd = Find-LineIndex -lines $lines -pattern '^\s{4}def\s+' -startIdx ($idxRecall + 1)
  if ($idxEnd -lt 0) { $idxEnd = $lines.Length }

  $recallHasTopkLocal = $false
  for ($i=$idxRecall; $i -lt $idxEnd; $i++) {
    if ($lines[$i] -match '^\s{8}topk\s*=\s*_clamp_topk\(') { $recallHasTopkLocal = $true; break }
  }

  for ($i=$idxRecall; $i -lt $idxEnd; $i++) {
    # default n: 6 -> VECTOR_TOPK_DEFAULT
    if ($lines[$i] -match '^\s{8}n:\s*int\s*=\s*6\s*,') {
      $lines[$i] = ($lines[$i] -replace '(\bn:\s*int\s*=\s*)6(\s*,)', '${1}VECTOR_TOPK_DEFAULT${2}')
      Write-Host "Patched recall() default n -> VECTOR_TOPK_DEFAULT."
      continue
    }

    # Insert local topk after out_docs init
    if (-not $recallHasTopkLocal -and ($lines[$i] -match '^\s{8}out_docs:\s*List\[str\]\s*=\s*\[\]\s*$')) {
      $refLines2 = [ref]$lines
      Insert-AfterLine -linesRef $refLines2 -idx $i -toInsert @("","        topk = _clamp_topk(n)","")
      $lines = $refLines2.Value
      $idxEnd += 3
      $recallHasTopkLocal = $true
      Write-Host "Inserted topk = _clamp_topk(n) in recall()."
      continue
    }

    # chat query n_results
    if ($lines[$i] -like "*n_results=max(1, int(n))*") {
      $lines[$i] = $lines[$i].Replace("n_results=max(1, int(n))", "n_results=topk")
      Write-Host "Patched chat coll.query n_results -> topk."
      continue
    }

    # global query n_results
    if ($lines[$i] -like "*n_results=max(1, int(max(3, n // 2)))*") {
      $lines[$i] = [regex]::Replace(
        $lines[$i],
        'n_results=max\(1,\s*int\(max\(3,\s*n\s*//\s*2\)\)\)\)',
        'n_results=max(3, int(topk // 2))'
      )
      Write-Host "Patched global coll.query n_results -> max(3, int(topk // 2))."
      continue
    }

    # unify slices + fallbacks inside recall (use topk instead of n)
    if ($recallHasTopkLocal) {
      $lines[$i] = [regex]::Replace($lines[$i], 'int\(n\)\s*\+\s*2', 'int(topk) + 2')
      $lines[$i] = [regex]::Replace($lines[$i], 'max\(1,\s*int\(n\)\)', 'max(1, int(topk))')
      $lines[$i] = [regex]::Replace($lines[$i], '\[-max\(1,\s*int\(n\)\)\:\]', '[-max(1, int(topk)):]')
      $lines[$i] = [regex]::Replace($lines[$i], 'hitsg\s*=\s*l\[-max\(1,\s*int\(n\)\)\:\]', 'hitsg = l[-max(1, int(topk)):]')
    }
  }

  # 3) Write back
  Set-Content -LiteralPath $Path -Value $lines -Encoding UTF8
  Write-Host "PATCH OK."

} catch {
  Write-Host ("PATCH FAILED -> auto-rollback to backup: " + $bakPath)
  Restore-File -src $bakPath -dst $Path
  throw
}
