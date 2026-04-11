param(
    [switch]$Apply,
    [string]$RepoRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -------------------------------------------------------------------
# MOSTY:
#  - Yavnyy: Git(index.lock) ↔ Codex contract preflight (fail-closed).
#  - Skrytyy #1: Windows ACL (icacls) ↔ determinizm payplayna (odinakovye checks).
#  - Skrytyy #2: A/B-slot ↔ bezopasnaya samo-redaktura (report-only vs apply).
#
# ZEMNOY ABZATs:
#  - It’s like a fuse in a panel: while the “DAY” line is on, the automation stalls.
#    We fix the power supply (ASL), and then the engine (live/potest) spins stably.
# -------------------------------------------------------------------

function _NowStamp { (Get-Date).ToString("yyyyMMdd_HHmmss") }

function _ResolveRepoRoot {
    param([string]$RepoRootArg)

    if ($RepoRootArg -and $RepoRootArg.Trim().Length -gt 0) {
        return (Resolve-Path $RepoRootArg).Path
    }
    # tools\ -> repo\
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function _WriteText {
    param([string]$Path, [string]$Text)
    Add-Content -Path $Path -Value $Text
}

function _InvokeNativeCapture {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Args
    )
    $out = @()
    try {
        $out = & $Exe @Args 2>&1 | ForEach-Object { "$_" }
    } catch {
        $out += "ERROR: $($_.Exception.Message)"
    }
    return $out
}

function _ParseDenyIdentities {
    param([string[]]$Lines)
    $ids = New-Object System.Collections.Generic.List[string]
    foreach ($ln in $Lines) {
        if (-not $ln) { continue }
        # line forms:
        #   <repo-root>\.git SID:(DENY)...
        #          SID:(OI)(CI)(IO)(DENY)...
        if ($ln -match '^\s*(?:\S+\s+)?(?<id>[^:]+):(?:\([A-Z]+\))*\(DENY\)') {
            $id = $Matches['id'].Trim()
            if ($id.Length -gt 0) { $ids.Add($id) }
        }
    }
    # unique
    return $ids | Sort-Object -Unique
}

function _ToIcaclsIdentity {
    param([string]$Identity)
    if (-not $Identity) { return $Identity }
    $id = $Identity.Trim()
    if ($id -match '^\*?S-1-[0-9-]+$') {
        $id = $id.TrimStart('*')
        return ("*{0}" -f $id)
    }
    return $id
}

function _InvokeRemoveDenyViaCmd {
    param(
        [string]$Path,
        [string]$Identity,
        [switch]$Recursive
    )
    if (-not $Path -or -not $Identity) { return @() }
    $scopeArg = if ($Recursive) { "/T /C" } else { "/C" }
    $cmd = ('icacls "{0}" /remove:d {1} {2}' -f $Path, $Identity, $scopeArg)
    return _InvokeNativeCapture -Exe "cmd.exe" -Args @("/d", "/c", $cmd)
}

function _TestLock {
    param([string]$LockPath, [string]$LogPath)
    try {
        New-Item -ItemType File -Force $LockPath -ErrorAction Stop | Out-Null
        Remove-Item -Force $LockPath -ErrorAction Stop
        _WriteText $LogPath "LOCK_OK"
        return $true
    } catch {
        _WriteText $LogPath ("LOCK_FAIL:{0}" -f $_.Exception.Message)
        return $false
    }
}

$repoRoot = _ResolveRepoRoot -RepoRootArg $RepoRoot

# hard safety: expected workdir in this project
$expected = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($repoRoot.TrimEnd('\') -ne $expected.TrimEnd('\')) {
    throw "WORKDIR violation: expected '$expected', got '$repoRoot'"
}

$ts = _NowStamp
$snapshotDir = Join-Path $repoRoot ("data\snapshots\{0}\iter16_git_index_acl" -f $ts)
$null = New-Item -ItemType Directory -Path $snapshotDir -Force

$reportFile = Join-Path $snapshotDir "report.txt"
$applyLogFile = Join-Path $snapshotDir "apply_log.txt"

$gitDir   = Join-Path $repoRoot ".git"
$index    = Join-Path $repoRoot ".git\index"
$lock     = Join-Path $repoRoot ".git\index.lock"

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$isAdmin = (New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
          ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

_WriteText $reportFile ("timestamp={0}" -f (Get-Date))
_WriteText $reportFile ("repo_root={0}" -f $repoRoot)
_WriteText $reportFile ("user={0}" -f $currentUser)
_WriteText $reportFile ("is_admin={0}" -f $isAdmin)
_WriteText $reportFile ("apply={0}" -f $Apply)

# Report current state
$icGit  = _InvokeNativeCapture -Exe "icacls" -Args @($gitDir)
$icIdx  = _InvokeNativeCapture -Exe "icacls" -Args @($index)

_WriteText $reportFile "----- icacls .git (head) -----"
$icGit | Select-Object -First 30 | ForEach-Object { _WriteText $reportFile $_ }

_WriteText $reportFile "----- icacls .git\index (all) -----"
$icIdx | ForEach-Object { _WriteText $reportFile $_ }

$denyGit = @(_ParseDenyIdentities -Lines $icGit)
$denyIdx = @(_ParseDenyIdentities -Lines $icIdx)

_WriteText $reportFile ("deny_git={0}" -f ($denyGit -join ","))
_WriteText $reportFile ("deny_index={0}" -f ($denyIdx -join ","))

if (-not $Apply) {
    Write-Host "[fix_git_index_acl] report: $reportFile"
    exit 0
}

# ----------------- APPLY (B-slot) -----------------
_WriteText $applyLogFile ("timestamp={0}" -f (Get-Date))
_WriteText $applyLogFile ("repo_root={0}" -f $repoRoot)
_WriteText $applyLogFile ("user={0}" -f $currentUser)
_WriteText $applyLogFile ("is_admin={0}" -f $isAdmin)

# backup index
$indexBak = Join-Path $snapshotDir "index.bak"
try {
    Copy-Item -Force $index $indexBak
    _WriteText $applyLogFile ("backup_index={0}" -f $indexBak)
} catch {
    _WriteText $applyLogFile ("backup_index=FAIL:{0}" -f $_.Exception.Message)
}

# best-effort remove lock
try {
    if (Test-Path $lock) {
        Remove-Item -Force $lock
        _WriteText $applyLogFile "removed_index_lock=1"
    } else {
        _WriteText $applyLogFile "removed_index_lock=0"
    }
} catch {
    _WriteText $applyLogFile ("removed_index_lock=FAIL:{0}" -f $_.Exception.Message)
}

# enable inheritance (best effort)
(_InvokeNativeCapture -Exe "icacls" -Args @($gitDir, "/inheritance:e", "/T", "/C")) | ForEach-Object { _WriteText $applyLogFile $_ }
(_InvokeNativeCapture -Exe "icacls" -Args @($index, "/inheritance:e", "/C")) | ForEach-Object { _WriteText $applyLogFile $_ }

# remove DENY identities (union)
$denyAll = @($denyGit + $denyIdx) | Sort-Object -Unique
foreach ($id in $denyAll) {
    $idArg = _ToIcaclsIdentity -Identity $id
    # remove deny on whole .git tree (best effort)
    (_InvokeRemoveDenyViaCmd -Path $gitDir -Identity $idArg -Recursive) | ForEach-Object { _WriteText $applyLogFile $_ }
    # and on index specifically
    (_InvokeRemoveDenyViaCmd -Path $index -Identity $idArg) | ForEach-Object { _WriteText $applyLogFile $_ }
}

# grant full to current user (avoid "$user:(..)" parsing by building string)
$grantTree = ("{0}:(OI)(CI)F" -f $currentUser)
$grantFile = ("{0}:F" -f $currentUser)

(_InvokeNativeCapture -Exe "icacls" -Args @($gitDir, "/grant", $grantTree, "/T", "/C")) | ForEach-Object { _WriteText $applyLogFile $_ }
(_InvokeNativeCapture -Exe "icacls" -Args @($index, "/grant", $grantFile, "/C")) | ForEach-Object { _WriteText $applyLogFile $_ }

# LOCK self-test
$lockOk = _TestLock -LockPath $lock -LogPath $applyLogFile

if (-not $lockOk) {
    _WriteText $applyLogFile "LOCK_REPAIR_FALLBACK_START"
    (_InvokeNativeCapture -Exe "takeown" -Args @("/F", $gitDir, "/R", "/D", "Y")) | ForEach-Object { _WriteText $applyLogFile $_ }
    (_InvokeNativeCapture -Exe "icacls" -Args @($gitDir, "/reset", "/T", "/C")) | ForEach-Object { _WriteText $applyLogFile $_ }
    (_InvokeNativeCapture -Exe "icacls" -Args @($gitDir, "/inheritance:e", "/T", "/C")) | ForEach-Object { _WriteText $applyLogFile $_ }
    (_InvokeNativeCapture -Exe "icacls" -Args @($gitDir, "/grant", $grantTree, "/T", "/C")) | ForEach-Object { _WriteText $applyLogFile $_ }
    (_InvokeNativeCapture -Exe "icacls" -Args @($index, "/grant", $grantFile, "/C")) | ForEach-Object { _WriteText $applyLogFile $_ }
    $lockOk = _TestLock -LockPath $lock -LogPath $applyLogFile
}

if ($lockOk) {
    _WriteText $applyLogFile "LOCK_OK"
    Write-Host "[fix_git_index_acl] report: $reportFile"
    Write-Host "[fix_git_index_acl] apply log: $applyLogFile"
    exit 0
} else {
    Write-Host "[fix_git_index_acl] report: $reportFile"
    Write-Host "[fix_git_index_acl] apply log: $applyLogFile"
    exit 2
}
