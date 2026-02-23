param()

$ErrorActionPreference = "Stop"

$touchList = @(
  "README.md",
  ".gitignore",
  "CITATION.cff",
  "SECURITY.md",
  "CONTRIBUTING.md",
  "CODE_OF_CONDUCT.md",
  "CHANGELOG.md",
  "AUTHORS.md",
  "TRADEMARK.md",
  "NOTICE",
  "docs/README.md",
  "docs/QUICKSTART.md",
  "docs/ARCHITECTURE.md",
  "docs/L4W_ALIGNMENT.md",
  "docs/THREAT_MODEL.md",
  "docs/RELEASE_CHECKLIST.md",
  "logo/README.md",
  "tools/scan_repo.ps1"
)

function Get-StagedText {
  param([string]$Path)

  $raw = @(git show --no-color ":$Path" 2>$null)
  if ($LASTEXITCODE -ne 0) {
    throw "Missing staged blob for '$Path'."
  }
  return ($raw -join "`n")
}

function Get-LineCount {
  param([string]$Text)

  if ([string]::IsNullOrEmpty($Text)) {
    return 0
  }
  return ($Text -split "`n").Count
}

function Assert-MinLines {
  param(
    [string]$Path,
    [int]$Min
  )

  $text = Get-StagedText -Path $Path
  $lineCount = Get-LineCount -Text $text
  if ($lineCount -lt $Min) {
    throw "Line-count gate failed for '$Path': $lineCount < $Min"
  }
  Write-Host ("[blob_gate] OK line-count: {0} => {1} lines (min {2})" -f $Path, $lineCount, $Min)
}

function Assert-NoCR {
  param([string]$Path)

  $text = Get-StagedText -Path $Path
  if ($text.Contains("`r")) {
    throw "CR check failed for '$Path': staged blob contains carriage returns."
  }
  Write-Host ("[blob_gate] OK no-CR: {0}" -f $Path)
}

Write-Host "[blob_gate] staging touch list..."
git add -- @touchList
if ($LASTEXITCODE -ne 0) {
  throw "git add failed for touch list."
}

Assert-MinLines -Path "README.md" -Min 80
Assert-MinLines -Path ".gitignore" -Min 40
Assert-MinLines -Path "CITATION.cff" -Min 8
Assert-MinLines -Path "docs/README.md" -Min 20
Assert-MinLines -Path "tools/scan_repo.ps1" -Min 80

$docs = @(git ls-files "docs/*.md" 2>$null | Sort-Object)
foreach ($docRel in $docs) {
  if ([string]::IsNullOrWhiteSpace($docRel)) {
    continue
  }
  if ([IO.Path]::GetFileName($docRel) -ieq "README.md") {
    continue
  }
  Assert-MinLines -Path $docRel -Min 30
}

$keyFiles = @(
  "README.md",
  ".gitignore",
  "CITATION.cff",
  "docs/README.md",
  "docs/QUICKSTART.md",
  "docs/ARCHITECTURE.md",
  "docs/L4W_ALIGNMENT.md",
  "docs/THREAT_MODEL.md",
  "docs/RELEASE_CHECKLIST.md",
  "tools/scan_repo.ps1"
)

foreach ($keyFile in $keyFiles) {
  Assert-NoCR -Path $keyFile
}

Write-Host "[blob_gate] PASS: staged-blob gates satisfied." -ForegroundColor Green
exit 0
