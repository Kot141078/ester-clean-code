# -*- coding: utf-8 -*-
"""
analyze_persona_shift.py

EXPLICIT BRIDGE (mezhkorpusnyy):
- Ashby: variety/control -> schitaem "raznoobrazie" stilya i ego sdvigi vo vremeni.
- Cover & Thomas: channel/capacity -> smotrim "propusknuyu sposobnost" (dlina/szhatost) otvetov kak signal ogranichitelya.
- Earth paragraph (anatomiya/inzheneriya): ANCHOR ~ stvol mozga; style/empathy ~ kora. Esli stvol podmenen, kora "plyvet".

(skrytye mosty): jaynes_prior, dhamma_signal
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

EMOJI_RE = re.compile(
    "["  # basic emoji ranges (good enough heuristic)
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)

CYR_RE = re.compile(r"[A-Yaa-yaEe]")
LAT_RE = re.compile(r"[A-Za-z]")

DEFAULT_INPUT = r"data\passport\clean_memory.jsonl"
DEFAULT_OUT_DIR = r"reports"


def _env_terms(name: str, default_csv: str = "") -> List[str]:
    raw = str(os.getenv(name, default_csv) or "")
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


OWNER_NAMES = _env_terms("ESTER_OWNER_GIVEN_NAMES")
OWNER_ALIASES = _env_terms("ESTER_OWNER_ALIASES")
ANCHOR_TERMS = _env_terms("ESTER_ANCHOR_TERMS", "anchor,yakor,sovereign")


@dataclass
class Row:
    idx: int
    ts: Optional[datetime]
    role: str
    text: str
    chars: int
    words: int
    emoji: int
    exclam: int
    quest: int
    dots: int
    cyr: int
    lat: int
    has_owner_name: int
    has_owner_alias: int
    has_anchor: int


def _safe_dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        # unix epoch?
        try:
            return datetime.fromtimestamp(float(v))
        except Exception:
            return None
    if isinstance(v, str):
        s = v.strip()
        # try ISO
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            pass
        # try common
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
    return None


def _count_words(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def _emoji_count(text: str) -> int:
    return len(EMOJI_RE.findall(text))


def _count_re(pat: str, text: str) -> int:
    return len(re.findall(pat, text))


def _as_text(rec: Dict[str, Any]) -> Tuple[str, str, Optional[datetime]]:
    # Common JSONL variants:
    # { "timestamp": "...", "role": "user"/"assistant", "text": "..." }
    # { "timestamp": "...", "role_user": "...", "role_assistant": "..." }
    # { "t": ..., "r": ..., "content": ... }
    ts = _safe_dt(rec.get("timestamp") or rec.get("time") or rec.get("t"))
    if "role" in rec and ("text" in rec or "content" in rec):
        role = str(rec.get("role", "unknown"))
        text = str(rec.get("text") or rec.get("content") or "")
        return role, text, ts

    # Pair format
    if "role_user" in rec or "role_assistant" in rec:
        # We'll yield two synthetic rows later; here just return combined.
        text_u = str(rec.get("role_user") or "")
        text_a = str(rec.get("role_assistant") or "")
        text = f"[USER]\n{text_u}\n\n[ASSISTANT]\n{text_a}".strip()
        return "pair", text, ts

    # fallback: stringify
    return "unknown", json.dumps(rec, ensure_ascii=False), ts


def load_rows(path: Path) -> List[Row]:
    rows: List[Row] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue

            role, text, ts = _as_text(rec)

            # If pair format, split into two logical entries (helps style drift).
            if role == "pair" and "[USER]" in text and "[ASSISTANT]" in text:
                u_text = text.split("[ASSISTANT]", 1)[0].replace("[USER]", "", 1).strip()
                a_text = text.split("[ASSISTANT]", 1)[1].strip()
                for sub_role, sub_text in (("user", u_text), ("assistant", a_text)):
                    rows.append(_mk_row(len(rows), ts, sub_role, sub_text))
            else:
                rows.append(_mk_row(len(rows), ts, role, text))
    return rows


def _mk_row(idx: int, ts: Optional[datetime], role: str, text: str) -> Row:
    text = text or ""
    chars = len(text)
    words = _count_words(text)
    emoji = _emoji_count(text)
    exclam = text.count("!")
    quest = text.count("?")
    dots = text.count("…") + _count_re(r"\.\.\.", text)
    cyr = len(CYR_RE.findall(text))
    lat = len(LAT_RE.findall(text))

    t_low = text.lower()
    has_owner_name = 1 if any(tok in t_low for tok in OWNER_NAMES) else 0
    has_owner_alias = 1 if any(tok in t_low for tok in OWNER_ALIASES) else 0
    has_anchor = 1 if any(tok in t_low for tok in ANCHOR_TERMS) else 0

    return Row(
        idx=idx,
        ts=ts,
        role=role,
        text=text,
        chars=chars,
        words=words,
        emoji=emoji,
        exclam=exclam,
        quest=quest,
        dots=dots,
        cyr=cyr,
        lat=lat,
        has_owner_name=has_owner_name,
        has_owner_alias=has_owner_alias,
        has_anchor=has_anchor,
    )


def _bucket_key(ts: Optional[datetime]) -> str:
    if ts is None:
        return "NO_TS"
    return ts.strftime("%Y-%m-%d")


def summarize(rows: List[Row]) -> Dict[str, Dict[str, float]]:
    by_day: Dict[str, List[Row]] = {}
    for r in rows:
        k = _bucket_key(r.ts)
        by_day.setdefault(k, []).append(r)

    out: Dict[str, Dict[str, float]] = {}
    for day, rr in sorted(by_day.items(), key=lambda x: x[0]):
        a = [x for x in rr if x.role.lower().startswith("assistant")]
        if not a:
            a = rr
        # jaynes_prior: tiny smoothing to avoid div/0
        eps = 1e-9

        out[day] = {
            "n": float(len(a)),
            "avg_chars": sum(x.chars for x in a) / (len(a) + eps),
            "avg_words": sum(x.words for x in a) / (len(a) + eps),
            "emoji_rate": sum(x.emoji for x in a) / (len(a) + eps),
            "exclam_rate": sum(x.exclam for x in a) / (len(a) + eps),
            "quest_rate": sum(x.quest for x in a) / (len(a) + eps),
            "dots_rate": sum(x.dots for x in a) / (len(a) + eps),
            "cyr_ratio": (sum(x.cyr for x in a) + eps) / (sum(x.cyr + x.lat for x in a) + eps),
            "has_owner_alias_rate": sum(x.has_owner_alias for x in a) / (len(a) + eps),
            "has_owner_name_rate": sum(x.has_owner_name for x in a) / (len(a) + eps),
        }
    return out


def detect_change_points(summary_by_day: Dict[str, Dict[str, float]]) -> List[Tuple[str, float, str]]:
    """
    Simple change detector: compare 7-day rolling mean before/after.
    Returns list of (day, score, reason).
    """
    days = [d for d in summary_by_day.keys() if d != "NO_TS"]
    days.sort()
    if len(days) < 16:
        return []

    def roll_mean(i0: int, i1: int, key: str) -> float:
        seg = days[i0:i1]
        return sum(summary_by_day[d][key] for d in seg) / max(1, len(seg))

    keys = ["avg_chars", "emoji_rate", "exclam_rate", "quest_rate", "cyr_ratio", "has_owner_alias_rate"]
    out: List[Tuple[str, float, str]] = []
    for i in range(7, len(days) - 7):
        score = 0.0
        reasons: List[str] = []
        for k in keys:
            before = roll_mean(i - 7, i, k)
            after = roll_mean(i, i + 7, k)
            diff = abs(after - before)
            # normalize loosely
            norm = max(0.1, abs(before))
            delta = diff / norm
            if delta > 0.6:  # heuristic threshold
                score += delta
                reasons.append(f"{k}: {before:.2f} -> {after:.2f}")
        if score > 2.0:
            out.append((days[i], score, "; ".join(reasons[:4])))
    out.sort(key=lambda x: x[1], reverse=True)
    return out[:10]


def write_report(rows: List[Row], summary_by_day: Dict[str, Dict[str, float]], changes: List[Tuple[str, float, str]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "persona_shift_report.md"
    csvp = out_dir / "persona_shift.csv"

    # CSV
    with csvp.open("w", encoding="utf-8") as f:
        f.write("day,n,avg_chars,avg_words,emoji_rate,exclam_rate,quest_rate,dots_rate,cyr_ratio,has_owner_alias_rate,has_owner_name_rate\n")
        for day, m in summary_by_day.items():
            f.write(
                f"{day},{int(m['n'])},{m['avg_chars']:.3f},{m['avg_words']:.3f},{m['emoji_rate']:.3f},"
                f"{m['exclam_rate']:.3f},{m['quest_rate']:.3f},{m['dots_rate']:.3f},{m['cyr_ratio']:.3f},"
                f"{m['has_owner_alias_rate']:.3f},{m['has_owner_name_rate']:.3f}\n"
            )

    # Markdown report
    dhamma_signal = "stil — eto sledstvie prichiny, a ne ukrashenie"
    with md.open("w", encoding="utf-8") as f:
        f.write("# Persona shift report (clean_memory.jsonl)\n\n")
        f.write(f"- Input rows: **{len(rows)}**\n")
        f.write(f"- Note: {dhamma_signal}\n\n")

        if changes:
            f.write("## Top change points (heuristic)\n\n")
            for day, score, reason in changes:
                f.write(f"- **{day}** score={score:.2f} :: {reason}\n")
            f.write("\n")
        else:
            f.write("## Change points\n\nNo strong change points detected (or slishkom malo dney s timestamp).\n\n")

        # Provide examples around first change point
        if changes:
            day0 = changes[0][0]
            f.write(f"## Samples around {day0}\n\n")
            # collect rows within +/- 1 day
            def day_of(r: Row) -> str:
                return _bucket_key(r.ts)

            targets = {day0}
            # naive +/- 1 day by lexicographic works for same month; good enough here
            for r in rows:
                if day_of(r) in targets and r.role.lower().startswith("assistant"):
                    f.write(f"### idx={r.idx} ts={r.ts} role={r.role}\n\n")
                    sample = r.text.strip()
