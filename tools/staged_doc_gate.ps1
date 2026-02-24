# Requires PowerShell 7+
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-GitRepository {
    $ok = git rev-parse --is-inside-work-tree 2>$null
    if (-not $ok) {
        throw "Not inside a git repository."
    }
}

function Get-StagedBlobSha {
    param([Parameter(Mandatory = $true)][string]$Path)
    $sha = (git rev-parse --verify --quiet ":$Path" 2>$null)
    if (-not $sha) {
        throw "File is not staged: $Path"
    }
    return ($sha | Select-Object -First 1).Trim()
}

function Get-StagedLineCount {
    param([Parameter(Mandatory = $true)][string]$Path)
    $count = (git show --no-textconv ":$Path" | Measure-Object -Line).Lines
    return [int]$count
}

function Get-StagedHasCR {
    param([Parameter(Mandatory = $true)][string]$Path)
    $sha = Get-StagedBlobSha -Path $Path
    $tmp = Join-Path $env:TEMP ("staged_blob_" + [Guid]::NewGuid().ToString("N") + ".bin")
    try {
        cmd /c "git cat-file -p $sha > `"$tmp`"" | Out-Null
        $bytes = [System.IO.File]::ReadAllBytes($tmp)
        return ($bytes -contains 13)
    }
    finally {
        Remove-Item -Force $tmp -ErrorAction SilentlyContinue
    }
}

Assert-GitRepository

$touchList = @(
    "README.md",
    "docs/SELF_EVO_OPTIN.md",
    "docs/README.md",
    "docs/THREAT_MODEL.md",
    "CHANGELOG.md",
    "CITATION.cff",
    "docs/RELEASE_CHECKLIST.md",
    "docs/RELEASE_NOTES_v0.2.3.md",
    "tools/staged_doc_gate.ps1"
)

git add -- $touchList

$rules = @(
    @{ Path = "README.md"; MinLines = 80 },
    @{ Path = "docs/SELF_EVO_OPTIN.md"; MinLines = 35 },
    @{ Path = "docs/README.md"; MinLines = 20 },
    @{ Path = "tools/staged_doc_gate.ps1"; MinLines = 60 }
)

$failures = @()
Write-Host "STAGED_LINE_COUNTS:"
foreach ($rule in $rules) {
    $path = [string]$rule.Path
    $minLines = [int]$rule.MinLines
    $lineCount = Get-StagedLineCount -Path $path
    $hasCR = Get-StagedHasCR -Path $path

    Write-Host ("{0} => {1} lines (min {2})" -f $path, $lineCount, $minLines)

    if ($lineCount -lt $minLines) {
        $failures += ("Line threshold failed for {0}: {1} < {2}" -f $path, $lineCount, $minLines)
    }
    if ($hasCR) {
        $failures += ("CR character found in staged blob: {0}" -f $path)
    }
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "STAGED_DOC_GATE=FAIL"
    foreach ($f in $failures) {
        Write-Host ("- " + $f)
    }
    exit 1
}

Write-Host ""
Write-Host "STAGED_DOC_GATE=PASS"
exit 0
