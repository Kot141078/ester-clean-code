param(
  [string]$ProjectRoot = (Get-Location).Path,
  [string]$TargetRel   = "run_ester_fixed.py",
  [string]$PythonRel   = ".\.venv\Scripts\python.exe"
)

function Write-UTF8NoBOM([string]$Path, [string]$Text) {
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Text, $utf8NoBom)
}

$Target = Join-Path $ProjectRoot $TargetRel
if (-not (Test-Path -LiteralPath $Target)) {
  throw "Target not found: $Target"
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$Target.bak_$stamp"
Copy-Item -LiteralPath $Target -Destination $bak -Force
Write-Host "[OK] Backup created: $bak"

$text = [System.IO.File]::ReadAllText($Target, (New-Object System.Text.UTF8Encoding($false)))

# -------------------------
# 1) Add Hippocampus.recent_entries (deterministic, no LLM)
# -------------------------
if ($text -notmatch "def\s+recent_entries\s*\(") {

  $method = @'
    def recent_entries(
        self,
        *,
        days: int = 7,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        topk: int = 8,
        include_global: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Deterministic memory read: return entries that realno zapisany za poslednie N dney.
        Bez LLM, bez pereskaza, bez "pokhozhe chto bylo".
        (Anatomicheskiy most: hippocampus — pro epizodicheskuyu pamyat; inzhenernyy most: audit-log po ts.)
        """
        try:
            days_i = max(1, int(days))
        except Exception:
            days_i = 7

        cutoff = int(time.time()) - (days_i * 86400)
        items: List[Dict[str, Any]] = []

        def _pull(coll) -> None:
            docs = []
            metas = []
            # Prefer where-filter by ts, fallback to manual filter
            try:
                got = coll.get(
                    where={"ts": {"$gte": cutoff}},
                    include=["documents", "metadatas"],
                    limit=max(50, topk * 20),
                )
                docs = got.get("documents") or []
                metas = got.get("metadatas") or []
            except Exception:
                try:
                    got = coll.get(include=["documents", "metadatas"], limit=max(200, topk * 50))
                    docs = got.get("documents") or []
                    metas = got.get("metadatas") or []
                except Exception:
                    return

            for d, m in zip(docs, metas):
                mm = m or {}
                ts = int(mm.get("ts") or 0)
                if ts and ts >= cutoff and (d or "").strip():
                    items.append({"ts": ts, "text": d, "meta": mm})

        # chat-local
        if chat_id is not None:
            try:
                _pull(self._get_chat_coll(chat_id=int(chat_id), user_id=user_id))
            except Exception:
                pass

        # global
        if include_global:
            try:
                _pull(self._get_global_coll())
            except Exception:
                pass

        # newest first
        items.sort(key=lambda x: int(x.get("ts") or 0), reverse=True)

        # simple dedupe by text
        seen = set()
        out: List[Dict[str, Any]] = []
        for it in items:
            t = (it.get("text") or "").strip()
            if not t:
                continue
            if t in seen:
                continue
            seen.add(t)
            out.append(it)
            if len(out) >= max(1, int(topk)):
                break
        return out
'@

  $marker = "`n    def _vector_peek_candidates_global"
  $idx = $text.IndexOf($marker)
  if ($idx -lt 0) {
    throw "[FAIL] Marker for Hippocampus insert not found: def _vector_peek_candidates_global"
  }
  $text = $text.Insert($idx, "`n$method`n")
  Write-Host "[OK] Inserted Hippocampus.recent_entries()"
} else {
  Write-Host "[WARN] Hippocampus.recent_entries already exists, skipping"
}

# -------------------------
# 2) Add memory-intent detector helpers (once)
# -------------------------
if ($text -notmatch "_MEM_INTENT_RE\s*=") {

  $helpers = @'
_MEM_INTENT_RE = re.compile(
    r"(?is)\b("
    r"chto\s+.*pomnish|poslednee\s+chto\s+pomnish|"
    r"za\s+posledn(ie|ikh)\s+\d+\s+dn|za\s+posledn(ie|ikh)\s+\d+\s+dney|"
    r"za\s+poslednyuyu\s+nedelyu|na\s+proshloy\s+nedele|"
    r"what\s+do\s+you\s+remember|last\s+\d+\s+days|last\s+week"
    r")\b"
)

def _is_memory_intent(user_text: str) -> bool:
    try:
        s = (user_text or "").strip()
    except Exception:
        return False
    if not s:
        return False
    return bool(_MEM_INTENT_RE.search(s))

def _extract_days(user_text: str, default: int = 7) -> int:
    s = (user_text or "")
    m = re.search(r"(?is)\b(\d{1,3})\s*(dn|dney|day|days)\b", s)
    if not m:
        return int(default)
    try:
        n = int(m.group(1))
        return max(1, min(90, n))
    except Exception:
        return int(default)
'@

  $marker = "`nasync def ester_arbitrage("
  $idx = $text.IndexOf($marker)
  if ($idx -lt 0) {
    throw "[FAIL] Marker not found: async def ester_arbitrage("
  }
  $text = $text.Insert($idx, "`n$helpers`n")
  Write-Host "[OK] Inserted _is_memory_intent/_extract_days helpers"
} else {
  Write-Host "[WARN] Memory-intent helpers already exist, skipping"
}

# -------------------------
# 3) Early-return in ester_arbitrage for memory questions (no hallucinations)
# -------------------------
if ($text -notmatch "brain\.recent_entries\(") {

  $guard = @'
    # --- memory-truth guard (no hallucinations) ---
    if _is_memory_intent(user_text):
        days = _extract_days(user_text, default=7)
        now_s = _format_now_for_prompt()
        entries = brain.recent_entries(days=days, chat_id=cid, user_id=uid, topk=8, include_global=True)

        if not entries:
            return f"Owner, u menya net zapisey v pamyati za poslednie {days} dney. (Seychas: {now_s})."

        try:
            tz = ZoneInfo("UTC")
        except Exception:
            tz = None

        lines = [f"Owner, vot chto u menya realno zapisano za poslednie {days} dney. (Seychas: {now_s})."]
        for it in entries:
            ts = int(it.get("ts") or 0)
            try:
                dt = datetime.datetime.fromtimestamp(ts, tz=tz or datetime.timezone.utc)
                when = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                when = str(ts)

            txt = (it.get("text") or "").strip().replace("\r", " ")
            txt = re.sub(r"\s+", " ", txt)
            lines.append(f"- {when}: {txt[:280]}")
        lines.append("Esli khochesh — day 2–3 klyuchevykh slova, i ya sdelayu bolee tochnyy poisk po pamyati.")
        return "\n".join(lines)

'@

  $marker = "    # --- recall memory ---"
  $idx = $text.IndexOf($marker)
  if ($idx -lt 0) {
    throw "[FAIL] Marker not found inside ester_arbitrage: '# --- recall memory ---'"
  }
  $text = $text.Insert($idx, $guard)
  Write-Host "[OK] Inserted memory-truth guard into ester_arbitrage()"
} else {
  Write-Host "[WARN] brain.recent_entries already referenced somewhere, skipping guard insert"
}

# -------------------------
# Write & compile
# -------------------------
Write-UTF8NoBOM -Path $Target -Text $text
Write-Host "[OK] Written patched file: $Target"

$Python = Join-Path $ProjectRoot $PythonRel
if (-not (Test-Path -LiteralPath $Python)) { $Python = "python" }

& $Python -m py_compile $Target
if ($LASTEXITCODE -ne 0) {
  Write-Host "[FAIL] py_compile failed. Rolling back..."
  Copy-Item -LiteralPath $bak -Destination $Target -Force
  throw "py_compile failed; rollback done"
}

Write-Host "[OK] py_compile passed"
Write-Host ""
Write-Host "If something goes wrong, rollback:"
Write-Host "Copy-Item -LiteralPath `"$bak`" -Destination `"$Target`" -Force"
