<# 
tools/update_evidence_hashes.ps1
Purpose: Update SHA256SUMS manifest for evidence/ pack (idempotent, with backup + rollback)

Explicit bridge: Cybernetics (Ashby) -> stability requires explicit feedback and controlled updates.
Hidden bridge #1: Physiology (Guyton/Hall) -> budgets/cooldowns prevent runaway oscillations.
Hidden bridge #2: Bayesian discipline (Jaynes) -> don't assert; measure + log + reproduce.

Earth paragraph:
This script treats your repo like wiring in a room: sloppy changes create ghost faults.
So we do: backup -> staged write -> verify -> atomic replace -> rollback if anything smells wrong.
#>

[CmdletBinding()]
param(
  [string]$RepoRoot = (Resolve-Path ".").Path,
  [string]$EvidenceDir = "evidence",
  [string]$ManifestPath = "",
  [switch]$DryRun,
  [switch]$NoMarkers
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function To-RelPath([string]$FullPath, [string]$Root) {
  $rel = $FullPath.Substring($Root.Length).TrimStart("\","/")
  return ($rel -replace "\\","/")
}

function Find-Manifest([string]$Root) {
  $candidates = @()

  $hashesDir = Join-Path $Root "hashes"
  if (Test-Path $hashesDir) {
    $candidates += Get-ChildItem $hashesDir -File -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -match '^SHA256SUMS.*\.(txt|md)$' -or $_.Name -match '^SHA256SUMS.*$' }
  }

  $candidates += Get-ChildItem $Root -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^SHA256SUMS.*\.(txt|md)$' -or $_.Name -match '^SHA256SUMS.*$' }

  if (-not $candidates -or $candidates.Count -eq 0) {
    throw "No SHA256SUMS manifest found under '$Root\hashes' or repo root."
  }

  # pick most recently modified
  return ($candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
}

function Compute-EvidenceLines([string]$Root, [string]$EvDir) {
  $evPath = Join-Path $Root $EvDir
  if (-not (Test-Path $evPath)) {
    throw "Evidence directory not found: $evPath"
  }

  $files = Get-ChildItem $evPath -Recurse -File | Sort-Object FullName
  if (-not $files -or $files.Count -eq 0) {
    throw "Evidence directory is empty: $evPath"
  }

  $lines = New-Object System.Collections.Generic.List[string]
  foreach ($f in $files) {
    $h = (Get-FileHash -Algorithm SHA256 -Path $f.FullName).Hash.ToLowerInvariant()
    $rel = To-RelPath $f.FullName $Root
    # canonical SHA256SUMS line: "<hash><two spaces><path>"
    $lines.Add("$h  $rel")
  }

  return $lines
}

function Update-ManifestWithMarkers([string]$Manifest, [System.Collections.Generic.List[string]]$NewLines) {
  $begin = "# BEGIN EVIDENCE PACK (auto)"
  $end   = "# END EVIDENCE PACK (auto)"

  $nl = "`r`n"
  $block = @(
    $begin
    ($NewLines -join $nl)
    $end
  ) -join $nl

  $raw = ""
  if (Test-Path $Manifest) {
    $raw = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8
  }

  # normalize to CRLF for Windows-friendly diffs
  $raw = ($raw -replace "`r?`n", $nl)

  if ($raw -match [regex]::Escape($begin) -and $raw -match [regex]::Escape($end)) {
    $pattern = [regex]::Escape($begin) + ".*?" + [regex]::Escape($end)
    $updated = [regex]::Replace($raw, $pattern, $block, "Singleline")
  } else {
    if (-not $raw.EndsWith($nl) -and $raw.Length -gt 0) { $raw += $nl }
    if ($raw.Length -gt 0) { $raw += $nl } # blank line before block
    $updated = $raw + $block + $nl
  }

  return @{ Text = $updated; Begin = $begin; End = $end }
}

function Update-ManifestNoMarkers([string]$Manifest, [System.Collections.Generic.List[string]]$NewLines) {
  $nl = "`r`n"
  $raw = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8
  $raw = ($raw -replace "`r?`n", $nl)

  # remove any existing lines for the same evidence paths (idempotent)
  $paths = $NewLines | ForEach-Object { ($_ -split "  ", 2)[1] }
  $escaped = $paths | ForEach-Object { [regex]::Escape($_) }
  $pattern = "^[a-f0-9]{64}\s{2}(" + ($escaped -join "|") + ")\s*$"
  $updatedLines = $raw -split $nl | Where-Object { $_ -notmatch $pattern }

  # append fresh lines
  if ($updatedLines.Count -gt 0 -and $updatedLines[-1].Trim() -ne "") {
    $updatedLines += ""
  }
  $updatedLines += $NewLines
  $updated = ($updatedLines -join $nl) + $nl
  return @{ Text = $updated; Begin = $null; End = $null }
}

function Safe-WriteFile([string]$TargetPath, [string]$NewText, [string[]]$MustContain) {
  $dir = Split-Path -Parent $TargetPath
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }

  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $bak = "$TargetPath.bak.$stamp"
  $tmp = "$TargetPath.tmp.$stamp"

  Copy-Item -LiteralPath $TargetPath -Destination $bak -Force

  # staged write
  [System.IO.File]::WriteAllText($tmp, $NewText, (New-Object System.Text.UTF8Encoding($false)))

  # verify
  $check = Get-Content -LiteralPath $tmp -Raw -Encoding UTF8
  foreach ($token in $MustContain) {
    if ($null -ne $token -and $token -ne "" -and ($check -notmatch [regex]::Escape($token))) {
      Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
      Copy-Item -LiteralPath $bak -Destination $TargetPath -Force
      throw "Verification failed: missing token '$token'. Rolled back to backup: $bak"
    }
  }

  # atomic replace-ish
  Move-Item -LiteralPath $tmp -Destination $TargetPath -Force
  return $bak
}

# --- main ---
$RepoRoot = (Resolve-Path $RepoRoot).Path
$evPath = Join-Path $RepoRoot $EvidenceDir
if (-not (Test-Path $evPath)) {
  throw "Evidence folder not found: $evPath"
}

if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
  $ManifestPath = Find-Manifest $RepoRoot
} else {
  $ManifestPath = (Resolve-Path $ManifestPath).Path
}

$lines = Compute-EvidenceLines $RepoRoot $EvidenceDir

if ($DryRun) {
  Write-Host "RepoRoot: $RepoRoot"
  Write-Host "Manifest: $ManifestPath"
  Write-Host "Evidence: $evPath"
  Write-Host ""
  $lines | ForEach-Object { Write-Host $_ }
  exit 0
}

$update = $null
if ($NoMarkers) {
  $update = Update-ManifestNoMarkers $ManifestPath $lines
  $must = @()
  # ensure at least one evidence file path exists in result
  $must += ($lines[0] -split "  ", 2)[1]
} else {
  $update = Update-ManifestWithMarkers $ManifestPath $lines
  $must = @($update.Begin, $update.End)
  # plus one concrete path check
  $must += ($lines[0] -split "  ", 2)[1]
}

$bakPath = Safe-WriteFile -TargetPath $ManifestPath -NewText $update.Text -MustContain $must

Write-Host "[OK] Updated manifest: $ManifestPath"
Write-Host "[OK] Backup saved:      $bakPath"
Write-Host ""
Write-Host "Next:"
Write-Host "  git add `"$EvidenceDir`" `"$ManifestPath`""
Write-Host "  git commit -m `"Update evidence pack hashes`""