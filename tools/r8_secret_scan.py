#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R8/tools/r8_secret_scan.py — grubaya offlayn-proverka na sekrety i risk-patterny.

Mosty:
- Yavnyy: Enderton — pravila kak predikaty (regex po strokam, spiski isklyucheniy) → determinirovannyy otchet.
- Skrytyy #1: Ashbi — konservativnyy regulyator: myagkie preduprezhdeniya, nichego ne lomaet.
- Skrytyy #2: Cover & Thomas — pinaem maksimum «signala» (vozmozhnye utechki), minimum «shuma» (ignor binari/bolshie fayly).

Zemnoy abzats (inzheneriya):
Skaniruet rabochuyu direktoriyu, propuskaya .git, venv, kartinki/arkhivy; ischet patterny `SECRET=`, `API_KEY`, `Bearer ...`,
`BEGIN PRIVATE KEY`, `telegram`, `password`. Vydaet Markdown-otchet, iskhodniki ne menyaet.

# c=a+b
"""
from __future__ import annotations
import argparse, os, re, hashlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
TEXT_EXT = {".py",".txt",".md",".json",".yaml",".yml",".ini",".cfg",".sh",".ps1",".http",".xml",".html",".htm"}
PATTERNS = [
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)secret\s*[:=]\s*[A-Za-z0-9_\-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\.\-_]{20,}"),
    re.compile(r"-----BEGIN (?:RSA|EC|PRIVATE) KEY-----"),
    re.compile(r"(?i)password\s*[:=]\s*[^,\s]{6,}"),
    re.compile(r"(?i)telegram"),
]

def _is_text(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in TEXT_EXT

def _iter_files(root: str):
    for dp, dns, fns in os.walk(root):
        base = os.path.basename(dp)
        if base in SKIP_DIRS:
            dns[:] = []  # ne uglublyaemsya
            continue
        for fn in fns:
            yield os.path.join(dp, fn)

def main() -> int:
    ap = argparse.ArgumentParser(description="Secret scan (offline)")
    ap.add_argument("--out", default="sec_report.md")
    args = ap.parse_args()

    findings = []
    for path in _iter_files(os.getcwd()):
        if not _is_text(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    for rx in PATTERNS:
                        if rx.search(line):
                            digest = hashlib.sha1(line.strip().encode("utf-8")).hexdigest()[:8]
                            findings.append((path, i, rx.pattern, digest))
        except Exception:
            continue

    lines = ["# Secret Scan Report\n"]
    if not findings:
        lines.append("Naydeno: 0 potentsialnykh problem.\n")
    else:
        lines.append(f"Naydeno: {len(findings)} potentsialnykh mest. **Prover vruchnuyu**.\n")
        lines.append("| File | Line | Pattern | SnipID |")
        lines.append("|------|------|---------|--------|")
        for p, i, patt, h in findings:
            lines.append(f"| `{p}` | {i} | `{patt}` | `{h}` |")
        lines.append("\n_Primechanie: SnipID — sha1 ot stroki (dlya navigatsii bez utechki teksta)._")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[r8_secret_scan] written: {args.out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

# c=a+b