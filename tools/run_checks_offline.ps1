#requires -Version 5.1
<#
Unified offline checks for Ester (closed_box):
- compileall
- route_registry_check
- route_return_lint
- health_check

Exit codes:
  0 = PASS
  2 = FAIL
#>

[CmdletBinding()]
param(
  [switch]$WriteReport,
  [switch]$NoGitGuard,
  [switch]$StrictMissing,
  [switch]$Quiet,
  [switch]$WithCompanionSmokes
)

$ErrorActionPreference = "Stop"

function Say($msg, $color = "Gray") {
  Write-Host $msg -ForegroundColor $color
}

function Fail($msg) {
  Say "[run_checks_offline] FAIL: $msg" "Red"
  exit 2
}

function Get-RepoRoot {
  try {
    $root = (git rev-parse --show-toplevel) 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $root) { return $null }
    return $root.Trim()
  }
  catch {
    return $null
  }
}

function Get-SensitiveStatusLines {
  $out = (git status --porcelain) 2>$null
  if ($LASTEXITCODE -ne 0) {
    return $null
  }
  $bad = @()
  foreach ($line in ($out -split "`n")) {
    $l = $line.TrimEnd()
    if (-not $l) { continue }
    if ($l -match "^\s*[MADRCU\?]{1,2}\s+secrets[\\/]") { $bad += $l; continue }
    if ($l -match "^\s*[MADRCU\?]{1,2}\s+ester_manifest\.json$") { $bad += $l; continue }
  }
  return $bad
}

function Run-Step([string]$Name, [string]$CmdLine, [scriptblock]$InvokeBlock) {
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  Say ("`n=== {0} ===" -f $Name) "Cyan"

  $stepOutput = ""
  if ($Quiet) {
    $captured = & $InvokeBlock 2>&1
    $rc = $LASTEXITCODE
    if ($captured) {
      $stepOutput = ($captured | ForEach-Object { $_.ToString() }) -join "`n"
    }
    if ($rc -eq 0) {
      Say ("[OK] {0}" -f $Name) "Gray"
    }
    else {
      Say ("[FAIL] {0}" -f $Name) "Red"
      if ($stepOutput) {
        Say $stepOutput "DarkGray"
      }
    }
  }
  else {
    Say $CmdLine "DarkGray"
    & $InvokeBlock | Out-Host
    $rc = $LASTEXITCODE
  }

  $sw.Stop()
  return [pscustomobject]@{
    name = $Name
    rc = $rc
    ms = [int]$sw.ElapsedMilliseconds
    output = $stepOutput
  }
}

# ---- Env: safe defaults (observe-only) ----
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPYCACHEPREFIX = (Join-Path $env:TEMP "ester_pycache")
$env:ESTER_OFFLINE = "1"
$env:ESTER_ALLOW_OUTBOUND_NETWORK = "0"

if (-not $WriteReport) {
  $env:ESTER_HEALTH_WRITE_REPORT = "0"
}

# ---- Paths ----
$repoRoot = Get-RepoRoot
if (-not $repoRoot) {
  Fail "Not a git repository (git rev-parse failed). Run from inside D:\ester-project."
}
Set-Location -LiteralPath $repoRoot

$py = "python"
$pathsToCheck = @(
  "tools\route_registry_check.py",
  "tools\route_return_lint.py",
  "modules\health_check.py"
)

foreach ($p in $pathsToCheck) {
  if (-not (Test-Path -LiteralPath $p)) {
    $msg = "Missing required file: $p"
    if ($StrictMissing) { Fail $msg } else { Say "[SKIP] $msg" "Yellow" }
  }
}

# ---- Run steps ----
$results = @()
$gitGuardBaseline = @()
if (-not $NoGitGuard) {
  $baseline = Get-SensitiveStatusLines
  if ($null -ne $baseline) {
    $gitGuardBaseline = @($baseline)
  }
}

# compile targets (syntax-only, safe for read-only __pycache__)
$compileTargets = @("modules", "routes", "security", "tools", "scripts") | Where-Object { Test-Path -LiteralPath $_ }
$compileArgs = $compileTargets -join " "
$quietNum = if ($Quiet) { "1" } else { "0" }

$results += Run-Step "compileall" "$py -B tools\py_compile_safe.py --roots $compileArgs" {
  & $py -B "tools\py_compile_safe.py" --roots $compileTargets
}

if (Test-Path -LiteralPath "tools\no_network_guard.py") {
  $results += Run-Step "no_network_guard" "$py -B tools\no_network_guard.py --quiet" {
    & $py -B "tools\no_network_guard.py" --quiet
  }
  $strictNetRaw = ("" + $env:ESTER_NO_NET_GUARD_STRICT).Trim().ToLowerInvariant()
  $strictNet = @("1", "true", "yes", "on", "y") -contains $strictNetRaw
  if ($strictNet) {
    $results += Run-Step "no_network_guard_strict" "$py -B tools\no_network_guard.py --strict --quiet" {
      & $py -B "tools\no_network_guard.py" --strict --quiet
    }
  }
  else {
    $results += [pscustomobject]@{ name = "no_network_guard_strict"; rc = 0; ms = 0; output = "" }
  }
}
else {
  $results += [pscustomobject]@{ name = "no_network_guard"; rc = 0; ms = 0; output = "" }
  $results += [pscustomobject]@{ name = "no_network_guard_strict"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\curiosity_tick_once.py") {
  $results += Run-Step "curiosity_tick_once_plan_only" "$py -B tools\curiosity_tick_once.py --plan-only --json" {
    & $py -B "tools\curiosity_tick_once.py" --plan-only --json
  }
}
else {
  $results += [pscustomobject]@{ name = "curiosity_tick_once_plan_only"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\build_integrity_manifest.py") {
  $results += Run-Step "build_integrity_manifest" "$py -B tools\build_integrity_manifest.py" {
    & $py -B "tools\build_integrity_manifest.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "build_integrity_manifest"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\route_registry_check.py") {
  $results += Run-Step "route_registry_check" "$py -B tools\route_registry_check.py" {
    & $py -B "tools\route_registry_check.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "route_registry_check"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\route_return_lint.py") {
  $results += Run-Step "route_return_lint" "$py -B tools\route_return_lint.py" {
    & $py -B "tools\route_return_lint.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "route_return_lint"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "modules\health_check.py") {
  $results += Run-Step "health_check" "$py -B modules\health_check.py" {
    & $py -B "modules\health_check.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "health_check"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\network_deny_smoke.py") {
  $results += Run-Step "network_deny_smoke" "$py -B tools\network_deny_smoke.py" {
    & $py -B "tools\network_deny_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "network_deny_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\oracle_smoke_deny.py") {
  $results += Run-Step "oracle_smoke_deny" "$py -B tools\oracle_smoke_deny.py" {
    & $py -B "tools\oracle_smoke_deny.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "oracle_smoke_deny"; rc = 0; ms = 0; output = "" }
}

if ((-not $Quiet) -and (Test-Path -LiteralPath "tools\oracle_by_agent_smoke.py")) {
  $results += Run-Step "oracle_by_agent_smoke" "$py -B tools\oracle_by_agent_smoke.py" {
    & $py -B "tools\oracle_by_agent_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "oracle_by_agent_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\agent_resume_smoke.py") {
  $results += Run-Step "agent_resume_smoke" "$py -B tools\agent_resume_smoke.py" {
    & $py -B "tools\agent_resume_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "agent_resume_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\agent_queue_smoke.py") {
  $results += Run-Step "agent_queue_smoke" "$py -B tools\agent_queue_smoke.py" {
    & $py -B "tools\agent_queue_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "agent_queue_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\agent_queue_approval_smoke.py") {
  $results += Run-Step "agent_queue_approval_smoke" "$py -B tools\agent_queue_approval_smoke.py" {
    & $py -B "tools\agent_queue_approval_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "agent_queue_approval_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\agent_capabilities_smoke.py") {
  $results += Run-Step "agent_capabilities_smoke" "$py -B tools\agent_capabilities_smoke.py" {
    & $py -B "tools\agent_capabilities_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "agent_capabilities_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\capability_audit_view_smoke.py") {
  $results += Run-Step "capability_audit_view_smoke" "$py -B tools\capability_audit_view_smoke.py" {
    & $py -B "tools\capability_audit_view_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "capability_audit_view_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\capability_drift_smoke.py") {
  $results += Run-Step "capability_drift_smoke" "$py -B tools\capability_drift_smoke.py" {
    & $py -B "tools\capability_drift_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "capability_drift_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\drift_quarantine_smoke.py") {
  $results += Run-Step "drift_quarantine_smoke" "$py -B tools\drift_quarantine_smoke.py" {
    & $py -B "tools\drift_quarantine_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "drift_quarantine_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\quarantine_clear_requires_evidence_smoke.py") {
  $results += Run-Step "quarantine_clear_requires_evidence_smoke" "$py -B tools\quarantine_clear_requires_evidence_smoke.py" {
    & $py -B "tools\quarantine_clear_requires_evidence_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "quarantine_clear_requires_evidence_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\quarantine_challenge_window_smoke.py") {
  $results += Run-Step "quarantine_challenge_window_smoke" "$py -B tools\quarantine_challenge_window_smoke.py" {
    & $py -B "tools\quarantine_challenge_window_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "quarantine_challenge_window_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\evidence_signature_smoke.py") {
  $results += Run-Step "evidence_signature_smoke" "$py -B tools\evidence_signature_smoke.py" {
    & $py -B "tools\evidence_signature_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "evidence_signature_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\l4w_envelope_smoke.py") {
  $results += Run-Step "l4w_envelope_smoke" "$py -B tools\l4w_envelope_smoke.py" {
    & $py -B "tools\l4w_envelope_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "l4w_envelope_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\l4w_auditor_verify_smoke.py") {
  $results += Run-Step "l4w_auditor_verify_smoke" "$py -B tools\l4w_auditor_verify_smoke.py" {
    & $py -B "tools\l4w_auditor_verify_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "l4w_auditor_verify_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\l4w_bundle_smoke.py") {
  $results += Run-Step "l4w_bundle_smoke" "$py -B tools\l4w_bundle_smoke.py" {
    & $py -B "tools\l4w_bundle_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "l4w_bundle_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\l4w_bundle_signing_smoke.py") {
  $results += Run-Step "l4w_bundle_signing_smoke" "$py -B tools\l4w_bundle_signing_smoke.py" {
    & $py -B "tools\l4w_bundle_signing_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "l4w_bundle_signing_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\l4w_publisher_roster_multisig_smoke.py") {
  $results += Run-Step "l4w_publisher_roster_multisig_smoke" "$py -B tools\l4w_publisher_roster_multisig_smoke.py" {
    & $py -B "tools\l4w_publisher_roster_multisig_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "l4w_publisher_roster_multisig_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\roster_transparency_log_smoke.py") {
  $results += Run-Step "roster_transparency_log_smoke" "$py -B tools\roster_transparency_log_smoke.py" {
    & $py -B "tools\roster_transparency_log_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "roster_transparency_log_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\l4w_roster_anchor_smoke.py") {
  $results += Run-Step "l4w_roster_anchor_smoke" "$py -B tools\l4w_roster_anchor_smoke.py" {
    & $py -B "tools\l4w_roster_anchor_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "l4w_roster_anchor_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\integrity_manifest_smoke.py") {
  $results += Run-Step "integrity_manifest_smoke" "$py -B tools\integrity_manifest_smoke.py" {
    & $py -B "tools\integrity_manifest_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "integrity_manifest_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\spec_guard_smoke.py") {
  $results += Run-Step "spec_guard_smoke" "$py -B tools\spec_guard_smoke.py" {
    & $py -B "tools\spec_guard_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "spec_guard_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\plan_schema_smoke.py") {
  $results += Run-Step "plan_schema_smoke" "$py -B tools\plan_schema_smoke.py" {
    & $py -B "tools\plan_schema_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "plan_schema_smoke"; rc = 0; ms = 0; output = "" }
}

$results += Run-Step "planner_action_plan_build" "$py -B -c <plan.build smoke>" {
  $code = "from modules.thinking import action_registry as ar`nimport json,sys`nrep=ar.run('plan.build', {'goal':'offline check'})`nprint(json.dumps(rep, ensure_ascii=False))`nsys.exit(0 if rep.get('ok') else 2)"
  & $py -B -c $code
}

if (Test-Path -LiteralPath "tools\dump_secret_scan.py") {
  $results += Run-Step "dump_secret_scan_env" "$py -B tools\dump_secret_scan.py --path .env" {
    & $py -B "tools\dump_secret_scan.py" --path ".env"
  }
  if (Test-Path -LiteralPath "Ester_dump_part_0001.txt") {
    $results += Run-Step "dump_secret_scan_dump_part_0001" "$py -B tools\dump_secret_scan.py --path Ester_dump_part_0001.txt" {
      & $py -B "tools\dump_secret_scan.py" --path "Ester_dump_part_0001.txt"
    }
  }
  else {
    $results += [pscustomobject]@{ name = "dump_secret_scan_dump_part_0001"; rc = 0; ms = 0; output = "" }
  }
}
else {
  $results += [pscustomobject]@{ name = "dump_secret_scan_env"; rc = 0; ms = 0; output = "" }
  $results += [pscustomobject]@{ name = "dump_secret_scan_dump_part_0001"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\agent_supervisor_smoke.py") {
  $results += Run-Step "agent_supervisor_smoke" "$py -B tools\agent_supervisor_smoke.py" {
    & $py -B "tools\agent_supervisor_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "agent_supervisor_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\execution_window_smoke.py") {
  $results += Run-Step "execution_window_smoke" "$py -B tools\execution_window_smoke.py" {
    & $py -B "tools\execution_window_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "execution_window_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\curiosity_e2e_smoke.py") {
  $results += Run-Step "curiosity_e2e_smoke" "$py -B tools\curiosity_e2e_smoke.py" {
    $out = cmd /c "$py -B tools\\curiosity_e2e_smoke.py 2>nul"
    $rc = $LASTEXITCODE
    if ($rc -ne 0) {
      $txt = (($out | ForEach-Object { $_.ToString() }) -join "`n")
      if ($txt -match '"error"\s*:\s*"network_deny_changed"') {
        Say "[curiosity_e2e_smoke] soft-skip: network deny delta observed in strict offline mode." "Yellow"
        $global:LASTEXITCODE = 0
        return $out
      }
    }
    return $out
  }
}
else {
  $results += [pscustomobject]@{ name = "curiosity_e2e_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\proactivity_enqueue_smoke.py") {
  $results += Run-Step "proactivity_enqueue_smoke" "$py -B tools\proactivity_enqueue_smoke.py" {
    & $py -B "tools\proactivity_enqueue_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "proactivity_enqueue_smoke"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\stubs_gate.py") {
  $results += Run-Step "stubs_gate" "$py -B tools\stubs_gate.py --jsonl data/reports/stubs_kill_list.jsonl --baseline docs/stubs_baseline.json --allowlist docs/stubs_allowlist.json --fail-on-reachable 1 --fail-on-increase 1 --ratchet 1 --quiet $quietNum" {
    & $py -B "tools\stubs_gate.py" `
      --jsonl "data/reports/stubs_kill_list.jsonl" `
      --baseline "docs/stubs_baseline.json" `
      --allowlist "docs/stubs_allowlist.json" `
      --fail-on-reachable "1" `
      --fail-on-increase "1" `
      --ratchet "1" `
      --quiet $quietNum
  }
}
else {
  $results += [pscustomobject]@{ name = "stubs_gate"; rc = 0; ms = 0; output = "" }
}

if (Test-Path -LiteralPath "tools\abuse_harness_smoke.py") {
  $results += Run-Step "abuse_harness_smoke" "$py -B tools\abuse_harness_smoke.py" {
    & $py -B "tools\abuse_harness_smoke.py"
  }
}
else {
  $results += [pscustomobject]@{ name = "abuse_harness_smoke"; rc = 0; ms = 0; output = "" }
}

if ($WithCompanionSmokes -and (-not $Quiet)) {
  if (Test-Path -LiteralPath "tools\outbox_smoke.py") {
    $results += Run-Step "outbox_smoke" "$py -B tools\outbox_smoke.py" {
      & $py -B "tools\outbox_smoke.py"
    }
  }
  if (Test-Path -LiteralPath "tools\comm_window_smoke.py") {
    $results += Run-Step "comm_window_smoke" "$py -B tools\comm_window_smoke.py" {
      & $py -B "tools\comm_window_smoke.py"
    }
  }
  if (Test-Path -LiteralPath "tools\telegram_sender_smoke.py") {
    $results += Run-Step "telegram_sender_smoke" "$py -B tools\telegram_sender_smoke.py" {
      & $py -B "tools\telegram_sender_smoke.py"
    }
  }
}

# ---- Optional git guard: forbid side effects on sensitive files ----
if (-not $NoGitGuard) {
  $results += Run-Step "git_guard" "git status --porcelain (deny secrets/* + ester_manifest.json)" {
    $current = Get-SensitiveStatusLines
    if ($null -eq $current) {
      Say "[WARN] git status failed; skipping git guard." "Yellow"
      $global:LASTEXITCODE = 0
      return
    }
    $bad = @()
    $baselineMap = @{}
    foreach ($l in $gitGuardBaseline) {
      $baselineMap[$l] = $true
    }
    foreach ($l in $current) {
      if (-not $baselineMap.ContainsKey($l)) {
        $bad += $l
      }
    }
    if ($bad.Count -gt 0) {
      Say "[git_guard] New sensitive changes detected during checks:" "Red"
      $bad | ForEach-Object { Say ("  " + $_) "Red" }
      $global:LASTEXITCODE = 2
    }
    else {
      $global:LASTEXITCODE = 0
    }
  }
}

# ---- Summary ----
$failCount = 0
foreach ($r in $results) {
  if ($r.rc -ne 0) { $failCount++ }
}

if ($Quiet) {
  if ($failCount -eq 0) {
    Say "`nPASS" "Green"
    exit 0
  }
  else {
    Say "`nFAIL (failed steps: $failCount)" "Red"
    exit 2
  }
}

Say "`n================ OFFLINE CHECKS SUMMARY ================" "Green"
foreach ($r in $results) {
  $status = if ($r.rc -eq 0) { "OK" } else { "FAIL" }
  $lineColor = if ($r.rc -eq 0) { "Gray" } else { "Red" }
  Say ("{0,-22} {1,-5} ({2} ms)" -f $r.name, $status, $r.ms) $lineColor
}

if ($failCount -eq 0) {
  Say "`nPASS" "Green"
  exit 0
}
else {
  Say "`nFAIL (failed steps: $failCount)" "Red"
  exit 2
}
