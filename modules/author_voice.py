# -*- coding: utf-8 -*-
"""modules/author_voice.py - “Voices avtora” dlya pisem i soobscheniy.

MOSTY:
- (Yavnyy) Post-obrabotka teksta (post persona_style) s uchetom predpochteniy avtora: teplee/koroche/formalnee, signatury.
- (Skrytyy #1) Passivnaya podstroyka pod auditoriyu: ne lomaet stil, a lish myagko korrektiruet registr/ritm.
- (Skrytyy #2) Bezopasnaya normalizatsiya: ne iskazhaet fakty, ne dobavlyaet “obmannykh” fraz, ne imitiruet cheloveka protiv pravil.

ZEMNOY ABZATs:
Daet Ester posledniy shtrikh - prevraschaet “pravilnyy” tekst v “my privychnyy” (rovno v granitsakh etiki i platform).

# c=a+b"""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DEFAULT_PATH = os.getenv("AUTHOR_VOICE_PATH", "config/author_voice.yaml")

@dataclass
class Voice:
    warmth: float = 0.3      # 0..1 (0 — sukho, 1 — teplo)
    brevity: float = 0.6     # 0..1 (1 — maksimalno kratko)
    formality: float = 0.7   # 0..1 (1 — ochen formalno)
    signature: str = ""      # dop. podpis (napr. «Owner»)
    prefix: str = ""         # greetings appeal (if necessary)

def _clip(x: float, lo=0.0, hi=1.0) -> float:
    return max(lo, min(hi, float(x)))

def load_voice(path: str = DEFAULT_PATH) -> Voice:
    try:
        import yaml
        if os.path.exists(path):
            data = yaml.safe_load(open(path, "r", encoding="utf-8")) or {}
            return Voice(
                warmth=_clip(data.get("warmth", 0.3)),
                brevity=_clip(data.get("brevity", 0.6)),
                formality=_clip(data.get("formality", 0.7)),
                signature=str(data.get("signature", "") or "").strip(),
                prefix=str(data.get("prefix", "") or "").strip(),
            )
    except Exception:
        pass
    return Voice()

def _de_canc(s: str) -> str:
    # soft de-“officialization”
    repl = {
        "osuschestvit": "sdelat",
        "neobkhodimo": "nuzhno",
        "po vysheukazannomu": "po ukazannomu",
        "vysheperechislennoe": "opisannoe vyshe",
        "in connection with which": "poetomu",
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    return s

def _limit_length(s: str, brevity: float) -> str:
    maxlen = 2000 - int(1200 * brevity)
    return s if len(s) <= maxlen else (s[:maxlen - 1] + "…")

def _formality_norm(s: str, formality: float) -> str:
    # in case of high formality, we remove interjections and emoticons; at low - allows a little softness
    if formality >= 0.8:
        for t in [":)", "😉", "😀", "👍", "!", "!!"]:
            s = s.replace(t, ".")
    if formality <= 0.3:
        # slegka druzhelyubno (bez infantilizma)
        s = s.replace("Proshu", "Please, please")
    return s

def _warmth_tone(s: str, warmth: float) -> str:
    if warmth >= 0.7 and "Spasibo" not in s and "S uvazheniem" not in s:
        s = s.rstrip()
        if not s.endswith(("!", ".", "…")):
            s += "."
        s += " Spasibo."
    return s

def apply_voice(text: str, voice: Voice) -> str:
    if not text:
        return text
    t = text.strip()
    t = _de_canc(t)
    t = _limit_length(t, voice.brevity)
    t = _formality_norm(t, voice.formality)
    t = _warmth_tone(t, voice.warmth)
    # Prefix and signature - if appropriate
    if voice.prefix and not t.lower().startswith(voice.prefix.lower()):
        t = f"{voice.prefix} {t}"
    if voice.signature and not t.rstrip().endswith(voice.signature):
        if not t.endswith((".", "!", "…")):
            t += "."
        t += f"\n{voice.signature}"
    return t

def render_with_voice(audience: str, intent: str, content: str, voice_overrides: Dict[str, Any] | None = None) -> str:
    # Render base text via person_style_is (postal layout) and then overlay voice
    from modules.persona_style_ext import render_email
    base = render_email(audience, intent, content)
    v = load_voice()
    if voice_overrides:
        for k, val in voice_overrides.items():
            if hasattr(v, k):
                setattr(v, k, val if not isinstance(getattr(v, k), float) else _clip(val))
    return apply_voice(base, v)