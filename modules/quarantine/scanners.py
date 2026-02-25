# -*- coding: utf-8 -*-
"""modules/quarantine/scanners.py - prostye staticheskie scanery: signatury riskovannykh vyzovov, tipizatsiya, skoring.

Mosty:
- Yavnyy: (Inzheneriya ↔ Bezopasnost) tekstovye Heuristics dlya Python/JS/HTML/shablonov.
- Skrytyy #1: (Infoteoriya ↔ Audit) vydaem obyasnimyy otchet s popadaniyami.
- Skrytyy #2: (Kibernetika ↔ Kontrol) nizkiy risk mozhno vypuskat v staging, vysokiy — only after revyu.

Zemnoy abzats:
Kak antivirus na minimalkakh: ischem opasnye instruktsii, schitaem risk, daem cheloveku ponyat, chto vnutri.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SIGNATURES = {
    "py": [
        (r"\bimport\s+os\b", 1, "os import"),
        (r"\bsubprocess\.", 3, "subprocess"),
        (r"\beval\(", 3, "eval"),
        (r"\bexec\(", 3, "exec"),
        (r"open\(/etc", 2, "system files"),
        (r"\burllib|requests\.", 1, "network"),
    ],
    "js": [
        (r"\beval\(", 3, "eval"),
        (r"\bXMLHttpRequest\b|\bfetch\(", 1, "network"),
        (r"\bchild_process\b", 3, "child process"),
    ],
    "html": [
        (r"<script\b", 1, "script tag")
    ],
    "any": [
        (r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----", 5, "private key"),
        (r"\bpassword\s*=", 2, "password literal"),
    ]
}

def _guess_lang(path: str, text: str) -> str:
    p = path.lower()
    if p.endswith(".py"): return "py"
    if p.endswith(".js"): return "js"
    if p.endswith(".html") or "<html" in text.lower(): return "html"
    return "txt"

def scan_bytes(raw: bytes, path: str) -> Dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception:
        text = ""
    lang = _guess_lang(path, text)
    findings: List[Dict[str, Any]] = []
    import re
    score = 0
    for (pat,w,why) in SIGNATURES.get("any",[])+SIGNATURES.get(lang,[]):
        for m in re.finditer(pat, text, re.IGNORECASE):
            findings.append({"offset": m.start(), "match": m.group(0)[:80], "why": why, "weight": w})
            score += w
    level = "low" if score<=1 else ("medium" if score<=4 else "high")
    return {"lang": lang, "score": score, "level": level, "findings": findings}
# c=a+b