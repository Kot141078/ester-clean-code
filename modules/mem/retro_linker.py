# -*- coding: utf-8 -*-
"""
modules/mem/retro_linker.py — avto-svyazyvanie suschnostey (KG↔gipotezy↔pamyat), «bez pereloma kontraktov».

Mosty:
- Yavnyy: (Memory ↔ KG) izvlekaem suschnosti iz novykh/svezhikh zapisey pamyati i pytaemsya upsert v KG + ostavlyaem ssylki.
- Skrytyy #1: (Gipotezy ↔ Memory) pri nakhozhdenii patternov ("esli..., to...") sozdaem zametku-gipotezu.
- Skrytyy #2: (Volya ↔ Planirovschik) modul dergaetsya kak ekshen «voli» ili po /ops/cron/tick.

Zemnoy abzats:
Eto «sekretar», kotoryy, chitaya dnevnik, risuet nitochki mezhdu imenami, mestami i ponyatiyami, chtoby potom bylo legche iskat.

# c=a+b
"""
from __future__ import annotations
import os, re, json, time, urllib.request
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("AUTOLINK_AB","A") or "A").upper()
DEFAULT_LIMIT = int(os.getenv("AUTOLINK_LIMIT","100") or "100")

# --- prosteyshiy izvlekatel suschnostey bez vneshnikh zavisimostey ---
EMAIL_RE   = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE     = re.compile(r"https?://[^\s)]+")
HASHTAG_RE = re.compile(r"(?:^|\s)#([A-Za-zA-Yaa-ya0-9_]{2,})")
PROPER_RE  = re.compile(r"\b([A-ZA-Ya][a-za-ya]+(?:\s+[A-ZA-Ya][a-za-ya]+){0,2})\b")

def extract_entities(text: str)->Dict[str, List[str]]:
    emails = list(set(EMAIL_RE.findall(text or "")))
    urls   = list(set(URL_RE.findall(text or "")))
    tags   = list(set([m.group(1) for m in HASHTAG_RE.finditer(text or "")]))
    names  = []
    for m in PROPER_RE.finditer(text or ""):
        token = m.group(1).strip()
        if len(token) >= 2: names.append(token)
    names = list(set(names))
    return {"names": names, "emails": emails, "urls": urls, "tags": tags}

# --- utility vyzova suschestvuyuschikh ruchek bez smeny ikh kontrakta ---
def _http_json(url: str, body: Dict[str,Any]|None=None, timeout: int=20)->Dict[str,Any]:
    data = json.dumps(body or {}).encode("utf-8") if body is not None else None
    req  = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"}) if body is not None else urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))
    
def _kg_upsert(node: Dict[str,Any])->None:
    try:
        # ozhidaem suschestvuyuschiy kg-rout (ne lomaem kontrakt)
        _http_json("http://127.0.0.1:8000/mem/kg/upsert", node)
    except Exception:
        pass

def _hypo_note(text: str, meta: Dict[str,Any])->None:
    try:
        _http_json("http://127.0.0.1:8000/mem/hypothesis/add", {"text": text, "meta": meta})
    except Exception:
        pass

def _passport(note:str, meta:Dict[str,Any])->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="autolink://retro")
    except Exception:
        pass

def _flashback(limit: int)->List[Dict[str,Any]]:
    try:
        rep = _http_json(f"http://127.0.0.1:8000/mem/flashback?limit={int(limit)}")
        if rep.get("ok"): return rep.get("items") or []
    except Exception:
        pass
    return []

# --- yadro: obrabotka zapisey pamyati ---
PATTERN_CAUSE = re.compile(r"\b(esli|when|kogda)\b.+\b(to|then)\b", re.IGNORECASE)

def process_item(item: Dict[str,Any])->Dict[str,Any]:
    text = str(item.get("text","") or item.get("body",""))
    meta = dict(item.get("meta") or {})
    ents = extract_entities(text)
    linked = {"kg":0,"hypo":0}
    if AB=="A":
        # KG uzly
        for n in ents["names"]:
            _kg_upsert({"kind":"PersonOrTerm","name":n})
            linked["kg"]+=1
        for u in ents["urls"]:
            _kg_upsert({"kind":"Url","url":u})
            linked["kg"]+=1
        for t in ents["tags"]:
            _kg_upsert({"kind":"Tag","tag":t})
            linked["kg"]+=1
        for e in ents["emails"]:
            _kg_upsert({"kind":"Email","email":e})
            linked["kg"]+=1
        # Gipotezy
        if PATTERN_CAUSE.search(text):
            _hypo_note(f"Gipoteza/pravilo iz pamyati: {text[:160]}", {"source":"retro_linker","ref":item.get("id","")})
            linked["hypo"]+=1
    return {"ok": True, "entities": ents, "linked": linked, "dry_run": AB!="A"}

def tick(limit: int|None=None)->Dict[str,Any]:
    L=int(limit or DEFAULT_LIMIT)
    items=_flashback(L)
    out=[]; k=0
    for it in items:
        rep=process_item(it); out.append(rep); k+= (rep.get("linked") or {}).get("kg",0)
    _passport("Avto-linkovka pamyati", {"count": len(items), "kg_links": k, "dry_run": AB!="A"})
    return {"ok": True, "checked": len(items), "report": out[-10:]}  # poslednie 10 dlya kratkosti
# c=a+b