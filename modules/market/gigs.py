# -*- coding: utf-8 -*-
"""
modules/market/gigs.py — «vakansii i otkliki»: parsing HTML/stranits, shablon pisma-otklika.

Mosty:
- Yavnyy: (Market ↔ Garazh/Ledzher) sobiraem zadachi, gotovim otkliki, vedem uchet.
- Skrytyy #1: (Legal/Quota ↔ Ostorozhnost) setevye zaprosy cherez legal_check i ingest_quota.
- Skrytyy #2: (Profile/KG ↔ Prozrachnost/Navigatsiya) shtampy i avtolink po opisaniyu vakansiy.

Zemnoy abzats:
Eto «priemnaya»: nashli vakansiyu — zapisali — podgotovili vezhlivyy otklik — dalshe ostanetsya nazhat «otpravit».

# c=a+b
"""
from __future__ import annotations
import os, json, time, re, urllib.request
from typing import Any, Dict, List
from modules.media.utils import legal_check, ingest_quota, passport, kg_autolink
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("MARKET_DB","data/market/gigs.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB): json.dump({"items":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _extract(html: str)->Dict[str,Any]:
    title = re.search(r"<h1[^>]*>(.*?)</h1>", html or "", re.I|re.S)
    budget= re.search(r"(?i)(Budget|Byudzhet)\s*:\s*([^<\\n]+)", html or "")
    loc   = re.search(r"(?i)(Remote|DefaultCity|Moskva|Berlin|Paris)", html or "")
    return {"title": (title.group(1).strip() if title else "Untitled"),
            "budget": (budget.group(2).strip() if budget else ""),
            "location": (loc.group(0).strip() if loc else "")}

def scan(items: List[Dict[str,Any]])->Dict[str,Any]:
    """
    items: [{"url": "...", "html": "..."}] — esli html ne zadan, popytaemsya skachat (best-effort).
    """
    out=[]
    for it in items or []:
        url=str(it.get("url","")); html=str(it.get("html","") or "")
        if not html and url:
            lg=legal_check("web_scrape","job_board")
            if lg.get("verdict")=="deny": continue
            qt=ingest_quota("jobs", 2)
            if not qt.get("allowed"): continue
            try:
                with urllib.request.urlopen(url, timeout=15) as r:
                    html=r.read().decode("utf-8","ignore")
            except Exception:
                html=""
        meta=_extract(html)
        rec={"t": int(time.time()), "url": url, "title": meta["title"], "budget": meta["budget"], "location": meta["location"]}
        out.append(rec)
    if out:
        j=_load(); j["items"]=(j.get("items") or []) + out; _save(j)
        try:
            kg_autolink([{"id": f"job-{i}", "text": f"{x['title']} {x['location']} {x['budget']}"} for i,x in enumerate(out)])
        except Exception: pass
        passport("gigs_scan", {"n": len(out)}, "market://scan")
    return {"ok": True, "items": out}

def letter(job: Dict[str,Any], profile: Dict[str,Any], tone: str="concise")->Dict[str,Any]:
    title= job.get("title","Opportunity")
    budget= job.get("budget","n/a")
    location= job.get("location","Remote")
    url= job.get("url","")
    name= profile.get("name","Ester")
    skills=", ".join(profile.get("skills") or [])
    links="; ".join(profile.get("links") or [])
    body=f"""Hello,

I’m {name}. I can help with “{title}”. Key strengths: {skills}.
I’m comfortable working {location.lower()} and can start quickly. Budget noted ({budget}). 
Portfolio: {links or '-'}.

If this fits, I’ll propose a short milestone to prove value fast.
Best regards,
{name}
"""
    passport("gigs_letter", {"title": title, "tone": tone}, "market://apply")
    return {"ok": True, "subject": f"{title} — application", "body": body.strip()}

def list_items(limit: int=50)->Dict[str,Any]:
    j=_load()
    return {"ok": True, "items": list(reversed(j.get("items",[])))[:max(1,int(limit))]}
# c=a+b