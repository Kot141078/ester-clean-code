param(
  [Parameter(Mandatory = $false)]
  [string]$Root = "."
)

# Iter9 note: scanner text is intentionally multiline and audit-readable.
# Keep policy checks explicit and line-separated for reviewability.

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $Root).Path

$excludeDirNames = @(
  ".git",
  ".hg",
  ".svn",
  ".venv",
  "venv",
  "env",
  "node_modules",
  "__pycache__",
  ".mypy_cache",
  ".pytest_cache",
  ".tox",
  "data",
  "state",
  "logs",
  "memory",
  "passport",
  "scroll",
  "chroma",
  "chromadb",
  "dumps",
  "manifests",
  "outbox",
  "out_reembed",
  "_ESTER_DUMP",
  "_tmp_corefacts_home",
  "artifacts",
  "dist",
  "build",
  "private",
  "Virtual Desktop for Ester"
)

$excludeRelativeFiles = @(
  "tools/scan_repo.ps1"
)

$binaryExtensions = @(
  ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".pdf",
  ".zip", ".gz", ".tar", ".7z", ".rar",
  ".exe", ".dll", ".so", ".dylib", ".bin", ".dat", ".run",
  ".db", ".sqlite", ".sqlite3",
  ".p12", ".pfx", ".pem", ".key", ".crt",
  ".mp3", ".mp4", ".avi", ".mov", ".wav",
  ".woff", ".woff2", ".ttf", ".eot",
  ".pyc", ".class", ".jar"
)

$emailAllowDomains = @(
  "example.com",
  "example.org",
  "example.net",
  "example.local",
  "acme.io",
  "corp.org",
  "proton.me",
  "noreply.local",
  "github.com",
  "localhost",
  "invalid",
  "test",
  "fsf.org",
  "gnu.org"
)

$lowContextKeywords = @("phone", "tel", "iban", "address", "mail", "email", "contact")

$patternSpecs = @(
  @{ Type = "PrivateKey"; Severity = "HIGH"; Regex = '-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----' },
  @{ Type = "WeakJwtFallback"; Severity = "HIGH"; Regex = '(?i)\bester[-]dev[-]secret\b' },
  @{ Type = "GitHubToken"; Severity = "HIGH"; Regex = '\bghp_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b' },
  @{ Type = "SlackToken"; Severity = "HIGH"; Regex = '\bxox[baprs]-[A-Za-z0-9-]{10,}\b' },
  @{ Type = "OpenAIToken"; Severity = "HIGH"; Regex = '\bsk-[A-Za-z0-9]{20,}\b' },
  @{ Type = "AuthorizationBearer"; Severity = "HIGH"; Regex = '(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._~+\-/=]{20,}' },
  @{ Type = "ClientSecret"; Severity = "HIGH"; Regex = '(?i)\bclient[_-]?secret\b\s*[:=]\s*[''\"]?[A-Za-z0-9._-]{8,}' },
  @{ Type = "TokenTailLogging"; Severity = "MEDIUM"; Regex = '(?i)\b\w*token\w*\s*\[\s*-\s*4\s*:\s*\]' },
  @{ Type = "EmailReal"; Severity = "MEDIUM"; Regex = '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b' },
  @{ Type = "AbsolutePath"; Severity = "LOW"; Regex = '(?i)\bC:\\Users\\|\bD:\\' },
  @{ Type = "PhoneLike"; Severity = "LOW"; Regex = '(?<!\d)(?:\+?\d[\d\s()\-]{8,}\d)(?!\d)' },
  @{ Type = "IBANLike"; Severity = "LOW"; Regex = '\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b' }
)

function Get-RelativePathCompat {
  param(
    [string]$BasePath,
    [string]$TargetPath
  )

  try {
    return [IO.Path]::GetRelativePath($BasePath, $TargetPath)
  }
  catch {
    $normalizedBase = $BasePath.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $baseUri = New-Object System.Uri($normalizedBase)
    $targetUri = New-Object System.Uri($TargetPath)
    $relativeUri = $baseUri.MakeRelativeUri($targetUri)
    return [System.Uri]::UnescapeDataString($relativeUri.ToString()).Replace('/', [IO.Path]::DirectorySeparatorChar)
  }
}

function Test-PathExcluded {
  param(
    [string]$Path,
    [string]$RootPath
  )

  $relativePath = Get-RelativePathCompat -BasePath $RootPath -TargetPath $Path
  $relativeUnix = $relativePath.Replace('\\', '/')
  if ($excludeRelativeFiles -contains $relativeUnix) {
    return $true
  }

  $segments = $Path.Split([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
  foreach ($segment in $segments) {
    if ([string]::IsNullOrWhiteSpace($segment)) {
      continue
    }
    if ($excludeDirNames -contains $segment) {
      return $true
    }
  }

  return $false
}

function Test-IsBinary {
  param([string]$Path)

  $ext = [IO.Path]::GetExtension($Path).ToLowerInvariant()
  if ($binaryExtensions -contains $ext) {
    return $true
  }

  $stream = [IO.File]::OpenRead($Path)
  try {
    $buffer = New-Object byte[] 4096
    $read = $stream.Read($buffer, 0, $buffer.Length)
    for ($i = 0; $i -lt $read; $i++) {
      if ($buffer[$i] -eq 0) {
        return $true
      }
    }
  }
  finally {
    $stream.Dispose()
  }

  return $false
}

function Get-CandidateFilePaths {
  param([string]$RootPath)

  $gitDir = Join-Path $RootPath ".git"
  if (Test-Path -LiteralPath $gitDir) {
    $tracked = @()
    $untracked = @()

    try {
      $tracked = @(git -c core.quotepath=false -C $RootPath ls-files 2>$null)
      $untracked = @(git -c core.quotepath=false -C $RootPath ls-files --others --exclude-standard 2>$null)
    }
    catch {
      $tracked = @()
      $untracked = @()
    }

    $relativePaths = @($tracked + $untracked | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
    if ($relativePaths.Count -gt 0) {
      $result = New-Object System.Collections.Generic.List[string]
      foreach ($relPath in $relativePaths) {
        $cleanRelPath = $relPath.Trim('\"')
        $fullPath = Join-Path $RootPath $cleanRelPath
        if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
          $result.Add((Resolve-Path -LiteralPath $fullPath).Path)
        }
      }
      return $result
    }
  }

  return @(Get-ChildItem -LiteralPath $RootPath -Recurse -File -Force | Select-Object -ExpandProperty FullName)
}

$findings = New-Object System.Collections.Generic.List[object]
$candidateFiles = Get-CandidateFilePaths -RootPath $resolvedRoot

foreach ($filePath in $candidateFiles) {
  if (Test-PathExcluded -Path $filePath -RootPath $resolvedRoot) {
    continue
  }

  if (Test-IsBinary -Path $filePath) {
    continue
  }

  try {
    $lines = Get-Content -LiteralPath $filePath -ErrorAction Stop
  }
  catch {
    continue
  }

  for ($lineIndex = 0; $lineIndex -lt $lines.Count; $lineIndex++) {
    $line = [string]$lines[$lineIndex]
    $lineLower = $line.ToLowerInvariant()

    foreach ($pattern in $patternSpecs) {
      if ($line -notmatch $pattern.Regex) {
        continue
      }

      if ($pattern.Type -eq "EmailReal") {
        $emailMatches = [regex]::Matches($line, $pattern.Regex)
        $hasRealEmail = $false
        foreach ($emailMatch in $emailMatches) {
          $domain = ($emailMatch.Value.Split("@")[-1]).ToLowerInvariant()
          if ($emailAllowDomains -notcontains $domain) {
            $hasRealEmail = $true
            break
          }
        }
        if (-not $hasRealEmail) {
          continue
        }
      }

      if (($pattern.Type -eq "PhoneLike") -or ($pattern.Type -eq "IBANLike")) {
        $hasKeyword = $false
        foreach ($keyword in $lowContextKeywords) {
          if ($lineLower.Contains($keyword)) {
            $hasKeyword = $true
            break
          }
        }
        if (-not $hasKeyword) {
          continue
        }
      }

      $preview = $line.Trim()
      if ($preview.Length -gt 160) {
        $preview = $preview.Substring(0, 160) + "..."
      }

      $relativePath = Get-RelativePathCompat -BasePath $resolvedRoot -TargetPath $filePath
      $findings.Add([PSCustomObject]@{
        Type = $pattern.Type
        Severity = $pattern.Severity
        File = $relativePath
        Line = $lineIndex + 1
        Preview = $preview
      })
    }
  }
}

$severityOrder = @("HIGH", "MEDIUM", "LOW")
Write-Host "Scan summary:" -ForegroundColor Cyan
foreach ($severity in $severityOrder) {
  $count = @($findings | Where-Object { $_.Severity -eq $severity }).Count
  Write-Host ("  {0}: {1}" -f $severity, $count)
}

if ($findings.Count -gt 0) {
  $findings |
    Sort-Object Severity, Type, File, Line |
    Format-Table Severity, Type, File, Line, Preview -AutoSize
}

$blockingCount = @($findings | Where-Object { $_.Severity -in @("HIGH", "MEDIUM") }).Count
if ($blockingCount -gt 0) {
  Write-Host "Scan failed: blocking findings detected ($blockingCount)." -ForegroundColor Red
  exit 1
}

if ($findings.Count -gt 0) {
  Write-Host "Scan passed with LOW-only findings." -ForegroundColor Yellow
}
else {
  Write-Host "Scan passed: no findings." -ForegroundColor Green
}

exit 0
