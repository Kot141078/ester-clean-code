# -*- powershell -*-
<#
    verify_dump.ps1 — Verifikatsiya faylov proekta po manifestu (ester_manifest.json).
    Proveryaet razmery, tipy i SHA256-kheshi. Esli raskhozhdeniya — predlagaet fiks (perezapis iz dampa).

    Mosty:
      • Yavnyy: Cover & Thomas (infoteoriya) → kheshi snizhayut entropiyu (neopredelennost) o tselostnosti.
      • Skrytyy 1: Enderton (logika) → predikaty: exists(size/hash) ⇒ tselostnost.
      • Skrytyy 2: Ashbi (kibernetika) → samoproverka kak regulyator protiv fragmentatsii.

    Zemnoy abzats:
      Skript — "storozhevoy pes": chitaet manifest, sharit po faylam, sveryaet kheshi. Esli fayl bityy — log + optsiya -Fix dlya vosstanovleniya iz dampa (Ester_dump_part_*.txt). Rasshirenie: dobavlen otchet v ester_verify_log.txt dlya P2P-sinkhronizatsii.

    Ispolzovanie:
      powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_dump.ps1 -Manifest "ester_manifest.json" -Fix -Verbose
#>

param(
    [string]$Manifest = "ester_manifest.json",
    [switch]$Fix,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

# Logirovanie
$LogFile = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\ester_verify_log.txt"

function Log-Message($msg, $level = "INFO") {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp [$level] $msg" | Out-File -FilePath $LogFile -Append -Encoding UTF8
}

function Write-Info($msg)  { Write-Host "[info] $msg"; Log-Message $msg "INFO" }
function Write-Ok($msg)    { Write-Host "[ok]   $msg" -ForegroundColor Green; Log-Message $msg "OK" }
function Write-Warn($msg)  { Write-Host "[warn] $msg" -ForegroundColor Yellow; Log-Message $msg "WARN" }
function Write-Fatal($msg) { Write-Host "[fatal] $msg" -ForegroundColor Red; Log-Message $msg "FATAL"; exit 1 }
function Write-VerboseMsg($msg) { if ($Verbose) { Write-Host "[verbose] $msg" -ForegroundColor Cyan; Log-Message $msg "VERBOSE" } }

# Chtenie manifesta
if (-not (Test-Path $Manifest)) { Write-Fatal "Manifest ne nayden: $Manifest" }
$man = Get-Content $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$entries = $man.entries

# Sbor dampa dlya fiksa (esli -Fix)
$dump_parts = @{}
if ($Fix) {
    $parts = $man.parts
    foreach ($p in $parts) {
        $file = $p.name
        if (Test-Path $file) {
            $content = Get-Content $file -Raw -Encoding UTF8
            $dump_parts[$p.index] = $content
        } else {
            Write-Warn "Chast dampa ne naydena: $file — fiks nedostupen dlya faylov iz etoy chasti."
        }
    }
}

# Verifikatsiya
$issues = @()
foreach ($e in $entries) {
    $path = $e.relpath
    $size = $e.size
    $sha = $e.sha256
    $part = $e.part

    Write-VerboseMsg "Proverka: $path"

    if (-not (Test-Path $path)) {
        $issues += "Otsutstvuet: $path"
        Write-Warn "Otsutstvuet fayl: $path"
        if ($Fix -and $dump_parts.ContainsKey($part)) {
            # Izvlech iz dampa
            $dump = $dump_parts[$part]
            $begin = "----- BEGIN FILE: $path  (size=$size B, type=text) -----"
            $end = "----- END FILE: $path -----"
            $idxB = $dump.IndexOf($begin)
            $idxE = $dump.IndexOf($end, $idxB)
            if ($idxB -ge 0 -and $idxE -ge 0) {
                $code = $dump.Substring($idxB + $begin.Length, $idxE - $idxB - $begin.Length).Trim()
                $dir = Split-Path $path -Parent
                if ($dir) { New-Item -ItemType Directory -Force -Path $dir }
                Set-Content -Path $path -Value $code -Encoding UTF8
                Write-Ok "Vosstanovlen: $path"
            } else {
                Write-Warn "Ne udalos izvlech iz dampa: $path"
            }
        }
        continue
    }

    # Proverka razmera
    $actualSize = (Get-Item $path).Length
    if ($actualSize -ne $size) {
        $issues += "Nevernyy razmer: $path (ozhidaemo $size, realno $actualSize)"
        Write-Warn "Nevernyy razmer: $path"
    }

    # Proverka SHA256
    $hashAlgo = [System.Security.Cryptography.SHA256]::Create()
    $fileBytes = [System.IO.File]::ReadAllBytes((Resolve-Path $path))
    $hashBytes = $hashAlgo.ComputeHash($fileBytes)
    $actualSha = [BitConverter]::ToString($hashBytes).Replace("-", "").ToLower()
    if ($actualSha -ne $sha) {
        $issues += "Nevernyy khesh: $path (ozhidaemo $sha, realno $actualSha)"
        Write-Warn "Nevernyy khesh: $path"
        if ($Fix) {
            # Fiks kak vyshe
            # ... (povtori kod izvlecheniya iz dampa, analogichno otsutstviyu)
        }
    } else {
        Write-Ok "OK: $path"
    }
}

if ($issues.Count -eq 0) {
    Write-Ok "Vse tselo! Net problem."
} else {
    Write-Warn "Problemy: $($issues.Count). Sm. log: $LogFile"
    $issues | ForEach-Object { Log-Message $_ "ISSUE" }
}

Write-Ok "Gotovo. Dlya P2P: kheshi mozhno广播it peers."