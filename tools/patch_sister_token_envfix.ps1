# tools\patch_sister_token_envfix.ps1
# A/B self-edit: A=backup, B=patched -> esli chto, otkat k A.
#
# YaVNYY MOST: c=a+b -> token (a, sekret) + normalizatsiya (b, protsedura) => sovpadenie strok (c, dopusk).
# SKRYTYE MOSTY:
#  - Ashby/variety: raznye sredy (Windows/Linux/dotenv) dayut raznye predstavleniya stroki — privodim k odnomu.
#  - Cover&Thomas: ogranichenie kanala — pokazyvaem tolko sha256 prefix, ne raskryvaya sekret tselikom.
# ZEMNOY ABZATs: kak prokladka na rezbe — ne menyaem “zhidkost”, ubiraem tolko podtekanie na styke (kavychki/BOM/CR).

param(
  [string]$EnvPath = "D:\ester-project\.env",
  [int]$Port = 8090
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-Sha256Prefix([string]$s, [int]$n=16) {
  $bytes = [Text.Encoding]::UTF8.GetBytes($s)
  $sha = [Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
  $hex = ($sha | ForEach-Object { $_.ToString("x2") }) -join ""
  return $hex.Substring(0, $n)
}

$full = (Resolve-Path $EnvPath).Path
$ts = (Get-Date).ToString("yyyyMMdd_HHmmss")
$bak = "$full.bak_envfix_$ts"

Copy-Item -LiteralPath $full -Destination $bak -Force
Write-Host "[INFO] Backup: $bak"

# chitaem bayty, dekodiruem UTF-8, ubiraem BOM esli est
$bytes = [System.IO.File]::ReadAllBytes($full)
$txt = [Text.Encoding]::UTF8.GetString($bytes)
if ($txt.Length -gt 0 -and $txt[0] -eq [char]0xFEFF) { $txt = $txt.Substring(1) }

# normalizuem perenosy
$txt = $txt -replace "`r`n", "`n"
$txt = $txt -replace "`r", "`n"

# helper: snyat tolko parnye obramlyayuschie kavychki
function Strip-WrappingQuotes([string]$v) {
  $v = ($v ?? "").Trim()
  if ($v.Length -ge 2) {
    $a = $v.Substring(0,1)
    $b = $v.Substring($v.Length-1,1)
    if (($a -eq $b) -and ($a -eq '"' -or $a -eq "'")) {
      return $v.Substring(1, $v.Length-2).Trim()
    }
  }
  return $v
}

# 1) PORT
if ($txt -match "(?m)^\s*PORT\s*=") {
  $txt = [regex]::Replace($txt, "(?m)^\s*PORT\s*=.*$", "PORT=$Port")
} else {
  $txt = $txt.TrimEnd("`n") + "`nPORT=$Port`n"
}

# 2) SISTER_SYNC_TOKEN (ne pokazyvaem znachenie, tolko normalizuem)
$tokenRaw = $null
$tokenNorm = $null

$m = [regex]::Match($txt, "(?m)^\s*SISTER_SYNC_TOKEN\s*=\s*(.+?)\s*$")
if ($m.Success) {
  $tokenRaw = $m.Groups[1].Value
  $tokenNorm = Strip-WrappingQuotes $tokenRaw

  # perepisyvaem stroku bez vneshnikh kavychek
  $txt = [regex]::Replace(
    $txt,
    "(?m)^\s*SISTER_SYNC_TOKEN\s*=.*$",
    ("SISTER_SYNC_TOKEN=" + $tokenNorm)
  )
  Write-Host ("[INFO] token sha256 prefix: " + (Get-Sha256Prefix $tokenNorm))
} else {
  Write-Host "[WARN] SISTER_SYNC_TOKEN not found in .env (nichego ne menyal po tokenu)."
}

# 3) Sokhranyaem UTF-8 bez BOM, vozvraschaem CRLF
$txt = $txt.TrimEnd("`n") + "`n"
$txt = $txt -replace "`n", "`r`n"

[System.IO.File]::WriteAllText($full, $txt, [System.Text.UTF8Encoding]::new($false))
Write-Host "[INFO] Saved (utf8 no bom): $full"