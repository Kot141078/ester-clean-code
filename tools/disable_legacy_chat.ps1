# tools/disable_legacy_chat.ps1
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$proj = Split-Path -Parent $root
$legacy = Join-Path $proj "routes\chat_api.py"
$disabled = Join-Path $proj "routes\__disabled__chat_api_legacy.py"

if (Test-Path $legacy) {
  Move-Item -Force $legacy $disabled
  Write-Host "[ok] legacy chat_api.py -> __disabled__chat_api_legacy.py"
} else {
  Write-Host "[skip] routes\chat_api.py ne nayden (uzhe otklyuchen?)"
}
