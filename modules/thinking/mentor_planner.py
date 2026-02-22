# -*- coding: utf-8 -*-
"""
modules/thinking/mentor_planner.py — «Nastavnik»: NL-zapros → plan podsvechivaemykh shagov.

Vkhod: stroka zaprosa, kontekst OS/okon (minimalno).
Vykhod: spisok shagov [{id, title, hint, action?, template_b64?, ocr?}]

Tipy shagov:
- "focus"  — fokus na okno/prilozhenie (action: {"type":"rpa.open","app":...} ili {"type":"window.focus","title":...})
- "click"  — podsvetit i po zaprosu kliknut (template_b64 | ocr)
- "type"   — podsvetit pole i vvesti tekst
- "info"   — tekstovaya podskazka bez deystviya

MOSTY:
- Yavnyy: (Rech ↔ Plan ↔ Deystvie) uchit na zhivom ekrane, a ne v tekste.
- Skrytyy #1: (Infoteoriya ↔ Zrenie) shagi imeyut yakorya (template|ocr) → determiniruem koordinaty.
- Skrytyy #2: (Kibernetika ↔ Volya) kazhdyy shag imeet «vypolnit» — zamknutaya petlya obucheniya.

ZEMNOY ABZATs:
Plan prostoy i rasshiryaemyy pravilami. Esli net shablonov — mozhno nachat s «focus/open» i pechati podskazki,
a potom dopolnyat shablonami. Rabotaet oflayn.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import re
from modules.thinking.intent_router import map_app_name, ensure_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def plan_from_request(text: str) -> Dict[str, Any]:
    q = (text or "").strip().lower()
    steps: List[Dict[str, Any]] = []

    # pravilo: «pokazhi kak polzovatsya <app>»
    m = re.search(r"pokazhi.*polzovatsya\s+([a-za-ya0-9\-_\.]+)", q)
    if m:
        app = map_app_name(m.group(1))
        steps.append({
            "id": "s1", "type": "focus", "title": f"Otkroem {app}",
            "hint": f"Zapustit/sfokusirovat {app}",
            "action": {"type": "rpa.open", "app": app}
        })
        # generic shagi dlya «bloknot / notepad»
        if app in ("notepad", "xterm", "chrome", "chromium"):
            steps += [
                {"id":"s2","type":"info","title":"Orientiruemsya","hint":"Posmotri na verkhnee menyu/kursor."},
                {"id":"s3","type":"type","title":"Pechat primera","hint":"Vvodim stroku v aktivnoe pole","action":{"type":"rpa.type","text":"Privet! Eto pokaz Ester."}},
            ]
        return {"ok": True, "name": f"teach_{app}", "steps": steps}

    # pravilo: «otkroy <app>»
    m = re.search(r"(otkroy|zapusti)\s+([a-za-ya0-9\-_\.]+)", q)
    if m:
        app = map_app_name(m.group(2))
        steps.append({"id":"s1","type":"focus","title":f"Otkroem {app}","hint":"Fokus/zapusk","action":{"type":"rpa.open","app":app}})
        return {"ok": True, "name": f"open_{app}", "steps": steps}

    # fallback
    return {"ok": True, "name": "help", "steps": [
        {"id":"s1","type":"info","title":"Skazhi: «pokazhi kak polzovatsya notepad»","hint":"Nachnem s prostogo primera"}
    ]}