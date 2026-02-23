# tools/mem_probe.ps1 — diagnostika putey pamyati Ester (sovmestim s Windows PowerShell 5.1)
param([string]$Root = (Get-Location).Path)

Write-Host "=== ENV ==="
"ESTER_DATA_ROOT=$env:ESTER_DATA_ROOT"
"ESTER_DATA_DIR=$env:ESTER_DATA_DIR"
"PERSIST_DIR=$env:PERSIST_DIR"
"ESTER_STATE_DIR=$env:ESTER_STATE_DIR"
"LMSTUDIO_URL=$env:LMSTUDIO_URL"
"OPENAI_API_BASE=$env:OPENAI_API_BASE"
"EMBED_MODEL=$env:EMBED_MODEL"

Write-Host "`n=== Guess roots (cwd/data/app variants) ==="
$roots = @(
  $Root,
  (Join-Path $Root 'data'),
  (Join-Path $Root 'data\app'),
  (Join-Path $Root 'app\data')
)

foreach ($r in $roots) {
  if (Test-Path $r) {
    Write-Host " - $r"
    # Bez -Depth dlya sovmestimosti: prosto ogranichim vyvod pervymi 5 elementami
    Get-ChildItem -Path $r -Directory -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'memory' } | Select-Object -First 5 | ForEach-Object {
      $_.FullName
      Get-ChildItem -Path $_.FullName -Filter *.json -Recurse -ErrorAction SilentlyContinue | Select-Object -First 5 | ForEach-Object {
        "   - " + $_.FullName
      }
    }
  }
}

Write-Host "`nTip: zapusti reembed tak:"
Write-Host "python .\scripts\memory_reembed.py --scan-only --report .\out_reembed\scan.json"
Write-Host "Esli politika vypolneniya meshaet: powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\mem_probe.ps1 -Root (Get-Location)"
