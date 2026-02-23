param(
  [string]$Path = ".\data\memory\memory.json"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $Path)) {
  Write-Host "[ERR] Not found: $Path"
  exit 2
}

# 1) Check first bytes
$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $Path))
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
  Write-Host "[INFO] BOM detected. Stripping..."
  python .\tools\strip_utf8_bom.py $Path
} else {
  Write-Host "[OK] No BOM."
}

# 2) JSON parse check
python -c "import json; p=r'$Path'; json.load(open(p,'r',encoding='utf-8')); print('OK_JSON:', p)"