#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S0/tools/diag_env_md.py — Markdown-otchet po peremennym okruzheniya i ikh kachestvu (offlayn).

Mosty:
- Yavnyy: Enderton (logika) — kazhdaya proverka formalizuetsya kak predikat nad (klyuch, znachenie), dayuschiy istinnost.
- Skrytyy #1: Ashbi (kibernetika) — A/B-slot: A=permissive (ne ronyaet), B=strict (podnimaet trevogu), s avtokatbekom.
- Skrytyy #2: Cover & Thomas (infoteoriya) — snizhaem «entropiyu» konfiguratsii: yavnyy spisok slabykh/pustykh sekretov.

Zemnoy abzats (inzheneriya):
Ne izmenyaet rantaym, tolko chitaet ENV i pishet Markdown. Polezno klast ryadom s relizom.
Po umolchaniyu pechataet v stdout; `--out env.md` — sokhranyaet v fayl. Bez vneshnikh zavisimostey.

# c=a+b
"""
from __future__ import annotations
import argparse
import os
import sys
import time
from typing import Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

RECOMMENDED: Dict[str, str] = {
    "APP_IMPORT": "app:app (ili wsgi_secure:app/wsgi:app)",
    "BASE_URL": "http://127.0.0.1:8080",
    "JWT_SECRET": "<64+ simvolov, HS256>",
    "JWT_TTL": "3600",
    "JWT_REFRESH_TTL": "1209600",
    "TELEGRAM_BOT_TOKEN": "<esli vklyuchen webhook>",
    "TELEGRAM_WEBHOOK_SECRET": "<sekret zagolovka>",
    "PUBLIC_URL": "https://host",
    "ADMIN_TELEGRAM_ID": "<chislovoy id, optsionalno>",
}

WEAK = {"JWT_SECRET": {"devsecret", "REPLACE_ME", "REPLACE_ME_WITH_64_CHAR_RANDOM"}}

def _weak(k: str, v: str | None) -> bool:
    if not v:
        return True
    if k in WEAK and v in WEAK[k]:
        return True
    return k == "JWT_SECRET" and len(v) < 32

def _render_md(rows: List[List[str]]) -> str:
    lines = ["# ENV report", ""]
    lines.append("| Key | Value (masked) | Status | Note |")
    lines.append("|-----|-----------------|--------|------|")
    lines.extend(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows)
    lines.append("")
    return "\n".join(lines)

def main() -> int:
    ap = argparse.ArgumentParser(description="Markdown-otchet po ENV")
    ap.add_argument("--out", default="-", help="Put k faylu vyvoda ili '-' dlya stdout")
    ap.add_argument("--mode", choices=["permissive","strict"], default=os.environ.get("CHECK_MODE","permissive"))
    args = ap.parse_args()

    rows: List[List[str]] = []
    problems = 0
    for k, descr in RECOMMENDED.items():
        raw = os.environ.get(k)
        masked = (raw[:4] + "…" + raw[-4:]) if raw and len(raw) > 12 else (raw or "")
        status = "OK"
        note = descr
        if _weak(k, raw):
            status = "WEAK" if raw else "MISSING"
            note = f"{descr} (ispravit)"
            problems += 1
        rows.append([f"`{k}`", f"`{masked}`", status, note])

    md = _render_md(rows)
    target = args.out
    if target != "-":
        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"[diag_env_md] Otchet zapisan v {target}")
        except Exception as e:
            print(f"[diag_env_md] WARN: ne udalos zapisat fayl: {e}")
            print(md)
    else:
        print(md)

    if args.mode == "strict" and problems:
        print(f"[diag_env_md] STRICT: naydeno problem: {problems}. Avtokatbek zapreschen v strict.", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())