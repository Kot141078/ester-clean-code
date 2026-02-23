# Appends an import block for the favicon WSGI hook into sitecustomize.py (idempotent).
param([string]$FilePath = "sitecustomize.py")

$ErrorActionPreference = "Stop"

if (!(Test-Path -Path $FilePath -PathType Leaf)) { Write-Error "sitecustomize.py not found: $FilePath"; exit 2 }

$marker = "# === [Ester-FAVICON-HOOK] import ==="
$block = @"
$marker
try:
    import ester.hooks.favicon_wsgi
except Exception:
    pass
"@

$txt = Get-Content $FilePath -Raw

# Use .Contains to avoid wildcard pitfalls with -like and square brackets
if ($txt.Contains($marker)) { Write-Host "[favicon-hook] Already present"; exit 0 }

$backup = "$FilePath.bak_favicon_{0}" -f (Get-Date -Format 'yyyyMMddHHmmss')
Copy-Item $FilePath $backup -Force

$new = $txt.TrimEnd() + "`r`n`r`n" + $block + "`r`n"
$new | Set-Content -Encoding UTF8 $FilePath
Write-Host "[favicon-hook] Patched $FilePath (backup at $backup)"
