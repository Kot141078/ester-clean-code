#requires -Version 5.1
<#
apply_patch_20251227_ctxq_v4_final.ps1
- Fixed: Function definition moved to top to prevent "CommandNotFoundException".
- Uses Python for the patching process to handle UTF-8 symbols (✨, …) correctly.
#>

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# --- FUNCTION DEFINITION MUST BE AT THE TOP ---
function _WriteUtf8Bom([string]$Path, [string]$Text) {
    # Write with BOM for compatibility
    $enc = [System.Text.Encoding]::UTF8
    $bytes = [System.Text.Encoding]::UTF8.GetPreamble() + [System.Text.Encoding]::UTF8.GetBytes($Text)
    [System.IO.File]::WriteAllBytes($Path, $bytes)
}

$ProjectDir = (Get-Location).Path
$Runner = Join-Path $ProjectDir "run_ester_fixed.py"
$ModuleDir = Join-Path $ProjectDir "modules"
$Module = Join-Path $ModuleDir "context_question_engine.py"

Write-Host ">>> CTXQ Patch V4.1 (Python-based + Fixed Scope)" -ForegroundColor Cyan
Write-Host "Target: $Runner"

if (!(Test-Path $Runner)) { throw "run_ester_fixed.py not found!" }

# --- 1. GENERATE PYTHON PATCHER ---
# We use Python to avoid PowerShell encoding issues with emoji/ellipsis matches
$PyPatcherScript = @'
import os
import sys

runner_path = sys.argv[1]
print(f"Reading {runner_path}...")

with open(runner_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Check if Module is imported (Safety check)
if "modules.context_question_engine" not in content:
    print("WARNING: Import block missing! Re-run V3 patch first or check file.")
    # We proceed anyway as V3 likely applied imports.

# 2. Define the exact string to replace (The one that failed in PS)
# Note: we match the exact indentation and symbols
needle = 'await context.bot.send_message(chat_id=int(ADMIN_ID), text=f"✨ Mysl prishla… {payload}")'

# The replacement block with CTXQ logic
replacement = r'''# CTXQ refine/replace
            try:
                if CTXQ_ENGINE and str(os.getenv("ESTER_CTXQ_ENABLED", "1")).lower() not in ("0","false","off"):
                    try:
                        from zoneinfo import ZoneInfo
                        _dt = datetime.datetime.fromtimestamp(_safe_now_ts(), tz=ZoneInfo("UTC"))
                    except: _dt = datetime.datetime.now()
                    _hist = []
                    try: _hist = short_term_by_key(str(ADMIN_ID))[-80:]
                    except: pass
                    _inp = CtxqInput(now=_dt, history=_hist, internal_state={"node": NODE_IDENTITY}, recalled=[], user_profile={"birthdate": os.getenv("ESTER_USER_BIRTHDATE", "")})
                    payload, _ = CTXQ_ENGINE.refine_or_replace(payload, _inp)
            except Exception: pass
            await context.bot.send_message(chat_id=int(ADMIN_ID), text=f"✨ Mysl prishla… {payload}")'''

if replacement in content:
    print("Already patched.")
    sys.exit(0)

# Try simple replace first
if needle in content:
    print("Found exact match. Patching...")
    new_content = content.replace(needle, replacement)
    
    with open(runner_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Success.")
    sys.exit(0)

# If exact match fails due to whitespace, try fuzzy line search
print("Exact match failed (indentation?). Trying fuzzy search...")
lines = content.splitlines()
modified = False
for i, line in enumerate(lines):
    if 'await context.bot.send_message' in line and '✨ Mysl prishla' in line and '{payload}' in line:
        # Get indentation
        indent = line[:len(line) - len(line.lstrip())]
        print(f"Found line {i+1} with indentation length {len(indent)}")
        
        # Indent the replacement block correctly
        # We manually construct the block lines to preserve indentation
        r_lines = replacement.splitlines()
        final_block = []
        for rl in r_lines:
            final_block.append(indent + rl.strip())
        
        lines[i] = "\n".join(final_block)
        modified = True
        break

if modified:
    with open(runner_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Success (fuzzy match).")
else:
    print("ERROR: Could not find the line to patch.")
    sys.exit(1)
'@

$PatcherFile = Join-Path $ProjectDir "temp_patcher_v4.py"
_WriteUtf8Bom -Path $PatcherFile -Text $PyPatcherScript

# --- 2. EXECUTE PYTHON PATCHER ---
try {
    Write-Host "Running Python patcher..." -ForegroundColor Cyan
    & python $PatcherFile $Runner
    if ($LASTEXITCODE -ne 0) {
        throw "Python patcher returned error code."
    }
} finally {
    Remove-Item $PatcherFile -ErrorAction SilentlyContinue
}

# --- 3. FINAL VERIFY ---
Write-Host "Verifying syntax..." -ForegroundColor Cyan
& python -m py_compile $Runner $Module
if ($LASTEXITCODE -eq 0) {
    Write-Host "PATCH V4.1 COMPLETE. CTXQ Logic is active." -ForegroundColor Green
} else {
    Write-Host "Syntax Error detected! Please check the file." -ForegroundColor Red
}