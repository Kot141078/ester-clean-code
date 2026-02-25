# -*- coding: utf-8 -*-
"""modules/garage/portfolio.py - sborka portfolio-sayta iz proektov garazha i ledzhera.

Mosty:
- Yavnyy: (Garazh/Ledzher ↔ Vitrina) staticheskiy sayt s kartochkami rabot i grafom balansa.
- Skrytyy #1: (Profile ↔ Prozrachnost) zapis o sborke v profile.
- Skrytyy #2: (RAG ↔ Kontent) short summary popadaet v poiskovuyu bazu fallback.

Zemnoy abzats:
This is “vitrina masterskoy”: raboty, dokhody, ssylki - chtoby odnim vzglyadom ponyat, chem my silny.

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict, List
from modules.media.utils import rag_append, passport
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

OUT = os.getenv("PORTFOLIO_DIR","data/garage/portfolio")

def _html(title: str, cards: List[Dict[str,Any]], totals: Dict[str,Any])->str:
    items=""
    for c in cards:
        items+=f"<div class='card'><h3>{c.get('id')}</h3><p>{c.get('kind')}</p><pre>{json.dumps(c.get('config') or {}, ensure_ascii=False)[:500]}</pre></div>"
    h=f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
    <style>body{{font-family:system-ui;padding:20px}}.grid{{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}}.card{{border:1px solid #ddd;border-radius:12px;padding:12px}}</style>
    </head><body><h1>{title}</h1>
    <h2>Balans: {totals.get('balance',0)} (dokhody {totals.get('totals',{}).get('income',0)} / raskhody {totals.get('totals',{}).get('expense',0)})</h2>
    <div class="grid">{items}</div></body></html>"""
    return h

def build()->Dict[str,Any]:
    os.makedirs(OUT, exist_ok=True)
    # gruzim proekty i finansy — cherez REST (universalnee)
    import urllib.request, json as _j
    with urllib.request.urlopen("http://127.0.0.1:8000/garage/project/list", timeout=5) as r:
        projs=_j.loads(r.read().decode("utf-8")).get("items",[])
    with urllib.request.urlopen("http://127.0.0.1:8000/finance/ledger/list", timeout=5) as r:
        fin=_j.loads(r.read().decode("utf-8"))
    html=_html("Ester — Portfolio", projs, fin)
    path=os.path.join(OUT,"index.html")
    open(path,"w",encoding="utf-8").write(html)
    # profile i RAG
    passport("portfolio_build", {"n": len(projs), "balance": fin.get("balance",0)}, "garage://portfolio")
    rag_append("portfolio-summary", f"projects:{len(projs)} balance:{fin.get('balance',0)}")
    return {"ok": True, "dir": OUT, "file": path, "projects": len(projs), "balance": fin.get("balance",0)}

def status()->Dict[str,Any]:
    path=os.path.join(OUT,"index.html")
    return {"ok": True, "exists": os.path.isfile(path), "file": path}
# c=a+b