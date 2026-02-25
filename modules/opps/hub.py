# -*- coding: utf-8 -*-
"""modules/opps/hub.py - khab vozmozhnostey (vakansii/zakazy): khranit, importirovat, menyat status.

Mosty:
- Yavnyy: (Garazh/Portfolio ↔ Outreach) Unified istochnik pravdy po “zakazam”.
- Skrytyy #1: (Profile ↔ Prozrachnost) dobavleniya/izmeneniya shtampuyutsya.
- Skrytyy #2: (Invoice/Finance ↔ Kontur) statusy “won→invoiced→paid” stykuyutsya so schetami.

Zemnoy abzats:
Kak CRM-bloknot: zametil zadachu — zapisal; doshel do predlozheniya - zafiksiroval; vyigral - perevel v finance.

# c=a+b"""
from __future__ import annotations
import os, json, time, hashlib, re, html
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("OPPS_DB","data/opps/opps.jsonl")
os.makedirs(os.path.dirname(DB), exist_ok=True)

STATUSES=("new","drafted","submitted","won","lost","invoiced","paid")

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "ops://opps")
    except Exception:
        pass

def _append(obj: dict)->None:
    with open(DB,"a",encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False)+"\n")

def _read_all()->List[Dict[str,Any]]:
    if not os.path.isfile(DB): return []
    out=[]
    with open(DB,"r",encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if not ln: continue
            try: out.append(json.loads(ln))
            except Exception: pass
    return out

def _id(fields: dict)->str:
    s=json.dumps(fields, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def add_or_update(d: dict)->dict:
    base={
        "title": str(d.get("title","")).strip(),
        "source": str(d.get("source","")).strip(),
        "url": str(d.get("url","")).strip(),
        "budget": float(d.get("budget",0.0) or 0.0),
        "currency": str(d.get("currency", os.getenv("OUTREACH_CURRENCY","EUR"))),
        "skills": list(d.get("skills") or []),
        "deadline": str(d.get("deadline","")),
        "status": str(d.get("status","new") if d.get("status") in STATUSES else "new")
    }
    oid=_id({"title": base["title"], "url": base["url"], "source": base["source"]})
    now=int(time.time())
    rec=dict(base, id=oid, t=now, notes=str(d.get("notes","")))
    _append(rec)
    _passport("opps_add", {"id": oid, "status": rec["status"]})
    return {"ok": True, "id": oid, "record": rec}

def list_all(status: str|None=None)->dict:
    items=_read_all()
    if status:
        items=[x for x in items if x.get("status")==status]
    # compact aggregation - latest ID
    seen=set(); uniq=[]
    for it in reversed(items):
        if it["id"] in seen: continue
        seen.add(it["id"]); uniq.append(it)
    uniq=list(reversed(uniq))
    return {"ok": True, "items": uniq}

def set_status(oid: str, status: str, notes: str="")->dict:
    if status not in STATUSES:
        return {"ok": False, "error":"bad_status", "allowed": STATUSES}
    _append({"id": oid, "status": status, "t": int(time.time()), "notes": notes, "event":"status"})
    _passport("opps_status", {"id": oid, "status": status})
    return {"ok": True, "id": oid, "status": status}

def _fetch(url: str)->str:
    if os.getenv("MEDIA_ALLOW_NETWORK","true").lower()!="true":
        return ""
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=20) as r:
            html_=r.read().decode("utf-8","ignore")
            return html_
    except Exception:
        return ""

def _extract(text: str)->dict:
    # very rude: title, budget, currency, emails
    title=""
    m=re.search(r"<title>(.*?)</title>", text, flags=re.I|re.S)
    if m: title=html.unescape(m.group(1)).strip()
    bud=0.0; cur=os.getenv("OUTREACH_CURRENCY","EUR")
    m=re.search(r"(\d[\d\s]{2,})(EUR|USD|\$|€)", text, flags=re.I)
    if m:
        bud=float(re.sub(r"\s+","",m.group(1)))
        cur=("USD" if "$" in m.group(2) else ("EUR" if "€" in m.group(2) else m.group(2).upper()))
    emails=re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return {"title": title or "Opportunity", "budget": bud, "currency": cur, "emails": list(sorted(set(emails)))}

def import_url(url: str, skills: list[str]|None=None)->dict:
    html=_fetch(url)
    if not html:
        return {"ok": False, "error":"fetch_blocked_or_failed"}
    meta=_extract(html)
    rec=add_or_update({"title": meta["title"], "source": "web", "url": url, "budget": meta["budget"], "currency": meta["currency"], "skills": skills or []})
    rec["record"]["emails"]=meta["emails"]
    _passport("opps_import", {"id": rec["id"], "emails": len(meta["emails"])})
    return {"ok": True, "id": rec["id"], "record": rec["record"]}
# c=a+b