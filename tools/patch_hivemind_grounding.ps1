param(
  [string]$Path = "D:\ester-project\run_ester_fixed.py"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path -LiteralPath $Path)) {
  throw "File not found: $Path"
}

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$Path.bak_$ts"
Copy-Item -LiteralPath $Path -Destination $bak -Force
Write-Host "[OK] Backup created: $bak"

$src = Get-Content -LiteralPath $Path -Raw -Encoding UTF8

# --- Patch 1: make temperature optional in _ask_provider signature (backward compatible)
$pat1 = "async def _ask_provider\(([^)]*?)temperature:\s*float(\s*,\s*max_tokens:\s*int\s*=\s*\d+\s*\)\s*:)"
if ($src -match $pat1) {
  $src2 = [regex]::Replace($src, $pat1, { param($m)
    $g1 = $m.Groups[1].Value
    $g2 = $m.Groups[2].Value
    "async def _ask_provider($g1" + "temperature: float = 0.7" + $g2
  }, 1)
  if ($src2 -ne $src) {
    $src = $src2
    Write-Host "[OK] Patched _ask_provider(): default temperature=0.7"
  } else {
    Write-Host "[WARN] _ask_provider() signature looks already patched."
  }
} else {
  Write-Host "[WARN] _ask_provider() signature pattern not found (maybe different formatting)."
}

# --- Patch 2: Ground HiveMind synthesize_thought (the global function with self param)
# Replace function block up to 'class Hippocampus:' (your file layout)
$pat2 = "(?s)async def synthesize_thought\(self, user_text: str, safe_history: list, base_system_prompt: str, identity_prompt: str, people_context: str, evidence_memory: str, file_context: str, facts_str: str, daily_report: str, temperature: float = 0\.7\) -> str:\s*.*?\n(?=class Hippocampus:)"
if ($src -match $pat2) {

$replacement = @'
async def synthesize_thought(self, user_text: str, safe_history: list, base_system_prompt: str, identity_prompt: str, people_context: str, evidence_memory: str, file_context: str, facts_str: str, daily_report: str, temperature: float = 0.7) -> str:
    """
    HiveMind synthesis WITH grounding:
    - collect pool of opinions (providers/sisters) as before
    - finalize via self._cascade_reply(), which injects:
        * current date/time context
        * memory/file/facts blocks
        * anti-hallucination constraints
    If cascade fails, fallback to old final prompt path.
    """
    import asyncio

    # safety: normalize history
    if safe_history is None:
        safe_history = []

    # richer system prompt for opinion gathering (keep it compact)
    ctx_bits = []
    if people_context:
        ctx_bits.append("[PEOPLE]\n" + str(people_context))
    if evidence_memory:
        ctx_bits.append("[MEMORY]\n" + str(evidence_memory))
    if file_context:
        ctx_bits.append("[FILES]\n" + str(file_context))
    if facts_str:
        ctx_bits.append("[FACTS]\n" + str(facts_str))
    if daily_report:
        ctx_bits.append("[DAILY]\n" + str(daily_report))

    sys_prompt = base_system_prompt
    if ctx_bits:
        sys_prompt = sys_prompt + "\n\n" + ("\n\n".join(ctx_bits))

    msgs = [{"role": "system", "content": sys_prompt}]

    # include short tail of history if it's in chat-format dicts
    try:
        tail = safe_history[-8:] if safe_history else []
        for h in tail:
            if isinstance(h, dict) and "role" in h and "content" in h:
                msgs.append({"role": h["role"], "content": h["content"]})
    except Exception:
        pass

    msgs.append({"role": "user", "content": user_text})

    # collect opinions
    opinion_tasks = []
    for p in getattr(self, "active", [])[:5]:
        # keep opinions slightly cooler
        opinion_tasks.append(self._ask_provider(p, msgs, temperature=0.6))
    try:
        if hasattr(self, "sisters") and isinstance(self.sisters, dict):
            for name in list(self.sisters.keys())[:2]:
                opinion_tasks.append(ask_sister_opinion(self, name, user_text))
    except Exception:
        pass

    opinions = await asyncio.gather(*opinion_tasks, return_exceptions=True)

    # build pool text
    blocks = []
    for op in opinions:
        if isinstance(op, Exception):
            blocks.append(f"[OPINION EXC] {type(op).__name__}: {op}")
        elif isinstance(op, dict):
            prov = op.get("provider", "unknown")
            err = op.get("error", "")
            txt = op.get("text", "")
            if err:
                blocks.append(f"[{prov}] ERROR: {err}")
            else:
                blocks.append(f"[{prov}]\n{txt}".strip())
        else:
            blocks.append(str(op).strip())

    pool_text = "\n\n".join([b for b in blocks if b])

    # finalization: use cascade (grounded)
    try:
        synth_model = self.pick_reply_synth()
        final_text = await self._cascade_reply(
            synth_model,
            base_system_prompt=base_system_prompt,
            identity_prompt=identity_prompt,
            people_context=people_context,
            evidence_memory=evidence_memory,
            evidence_web="",
            file_context=file_context,
            pool_text=pool_text,
            facts_str=facts_str,
            daily_report=daily_report,
            safe_history=safe_history,
            user_text=user_text,
            temperature=temperature
        )
        return _clean_ester_response(str(final_text)).strip()
    except Exception as e:
        # fallback to old behavior
        final = self.pick_reply_final()
        final_prompt = [
            {"role": "system", "content": f"{identity_prompt}\n\n[POOL]\n{pool_text}\n\nPravila: ne vydumyvay. Esli v pamyati net — skazhi chestno, chto ne pomnish."},
            {"role": "user", "content": user_text}
        ]
        final_text = await _safe_chat(final, final_prompt, temperature=temperature, max_tokens=1200)
        return _clean_ester_response(str(final_text)).strip()

'@

  $src = [regex]::Replace($src, $pat2, $replacement, 1)
  Write-Host "[OK] Patched HiveMind synthesize_thought(): grounded via _cascade_reply()"
} else {
  Write-Host "[WARN] synthesize_thought() block not found (signature/layout differs)."
}

Set-Content -LiteralPath $Path -Value $src -Encoding UTF8
Write-Host "[OK] Written patched file: $Path"

# quick compile check
try {
  & "D:\ester-project\.venv\Scripts\python.exe" -m py_compile $Path
  Write-Host "[OK] py_compile passed"
} catch {
  Write-Host "[FAIL] py_compile failed: $($_.Exception.Message)"
  Write-Host "Rollback:"
  Write-Host "Copy-Item -LiteralPath `"$bak`" -Destination `"$Path`" -Force"
  exit 2
}

Write-Host ""
Write-Host "Rollback (if needed):"
Write-Host "Copy-Item -LiteralPath `"$bak`" -Destination `"$Path`" -Force"
