# -*- coding: utf-8 -*-
"""R3/services/reco/tokenizer.py - prostaya tokenizatsiya RU/EN (stdlib), bez vneshnikh zavisimostey.

Mosty:
- Yavnyy: Enderton (logika) — tokenizatsiya kak proveryaemye predikaty nad simvolami/klassami, daet determinirovannyy result.
- Skrytyy #1: Cover & Thomas (infoteoriya) — filtratsiya stop-slov snizhaet "shum" i povyshaet otnoshenie signal/shum.
- Skrytyy #2: Ashbi (kibernetika) — A/B-slot: A=unigrammy, B=unigrammy+bigrammy; pri oshibke B ⇒ avtootkat v A.

Zemnoy abzats:
Use tolko stdlib: regex dlya slov, nizhniy registr, korotkie stop-listy ru/en.
V rezhime B dobavlyaem bigrammy iz sosednikh tokenov. Podkhodit dlya CPU low class (N100).

# c=a+b"""
from __future__ import annotations
import os
import re
from typing import Iterable, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_WORD_RE = re.compile(r"[0-9A-Za-zA-Yaa-yaEe_]{2,}", re.UNICODE)

STOP_RU = {
    "i","v","vo","na","s","so","k","do","po","za","iz","u","ot","dlya","o","ob","no","a",
    "kak","chto","eto","to","zhe","ne","da","li","by","chtoby","pri","nad","pod","ikh","my",
    "vy","on","ona","oni","ono","ikh","ee","emu","ee","ego","ya","ty","vam","nam","tut","tam",
}
STOP_EN = {
    "the","a","an","in","on","of","for","to","and","or","but","is","are","be","been","was",
    "were","with","without","by","as","at","it","this","that","those","these","we","you",
    "he","she","they","i","me","my","your","our","their","from",
}

def _is_stop(w: str) -> bool:
    lw = w.lower()
    return lw in STOP_RU or lw in STOP_EN or len(lw) <= 2

def tokenize(text: str) -> List[str]:
    tokens = [m.group(0).lower() for m in _WORD_RE.finditer(text)]
    toks = [t for t in tokens if not _is_stop(t)]
    mode = (os.getenv("R3_MODE") or "A").strip().upper()
    if mode == "B":
        try:
            bigrams = [a + "_" + b for a, b in zip(toks, toks[1:])]
            return toks + bigrams
        except Exception:
            # Avtokatbek
            return toks
    return toks