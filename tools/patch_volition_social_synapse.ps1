# tools\patch_volition_social_synapse.ps1
param(
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){   Write-Host "[OK]  $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err($m){  Write-Host "[ERR]  $m" -ForegroundColor Red }

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root     = Split-Path -Parent $toolsDir

Info "Repo root: $root"

# 1) find a Python file that contains a standalone call: self.social_synapse_cycle(...)
$pyFiles = Get-ChildItem -Path $root -Recurse -Filter "*.py" -File |
  Where-Object { $_.FullName -notmatch "\\\.venv\\|\\vstore\\|\\logs\\|\\__pycache__\\" }

$candidates = New-Object System.Collections.Generic.List[string]
foreach($f in $pyFiles){
  try{
    $hit = Select-String -Path $f.FullName -Pattern "self.social_synapse_cycle(" -SimpleMatch -ErrorAction SilentlyContinue
    if($hit){ $candidates.Add($f.FullName) }
  } catch {}
}

if($candidates.Count -eq 0){
  Warn "No files with 'self.social_synapse_cycle(' found. Nothing to patch."
  exit 0
}

$target = $candidates[0]
Info "Target file: $target"

# If the method already exists somewhere, don't touch
$raw = Get-Content -Path $target -Raw -Encoding UTF8
if($raw -match "def\s+social_synapse_cycle\s*\("){
  Ok "social_synapse_cycle already exists in target. Nothing to do."
  exit 0
}

$lines = Get-Content -Path $target -Encoding UTF8

$patched = $false
$out = New-Object System.Collections.Generic.List[string]

foreach($line in $lines){
  if($line -match '^(?<indent>\s*)self\.social_synapse_cycle\((?<args>.*)\)\s*$'){
    $indent = $Matches['indent']
    $args   = $Matches['args']

    # Guarded call
    $out.Add("${indent}if hasattr(self, `"social_synapse_cycle`"):")
    $out.Add("${indent}    self.social_synapse_cycle($args)")
    $patched = $true
  } else {
    $out.Add($line)
  }
}

if(-not $patched){
  Warn "Found the token, but not as a standalone line. No safe patch applied."
  Warn "Open the file and locate the call; wrap it with hasattr(self, 'social_synapse_cycle')."
  exit 2
}

$stamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$bak = "$target.bak_$stamp"

Copy-Item -Path $target -Destination $bak -Force
Info "Backup created: $bak"

if($DryRun){
  Info "DryRun enabled: not writing changes."
  exit 0
}

# Write back (keep UTF-8)
Set-Content -Path $target -Value $out -Encoding UTF8
Ok "Patched file saved."

# Compile-check (auto-rollback on failure)
Info "Running py_compile on patched file..."
& python -m py_compile $target
if($LASTEXITCODE -ne 0){
  Err "py_compile FAILED. Rolling back..."
  Copy-Item -Path $bak -Destination $target -Force
  Err "Rollback done."
  exit 1
}

Ok "py_compile OK. Volition hotfix applied."
Info "Restart Ester now."