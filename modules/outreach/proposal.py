# modules/outreach/proposal.py
# -*- coding: utf-8 -*-
"""modules/outreach/proposal.py - generator predlozheniy/pisem po vozmozhnosti (oflayn MD/HTML + email).

Mosty:
- Yavnyy: (Opps ↔ Outreach) iz kartochki vozmozhnosti — srazu gotovoe predlozhenie i pismo.
- Skrytyy #1: (Portfolio/Invoices ↔ Vitrina/Dok-oborot) ssylkami vstraivaetsya portfolio i schet.
- Skrytyy #2: (Passport/RAG ↔ Prozrachnost/Poisk) teksty otpravlyayutsya v RAG i shtampuyutsya.

Zemnoy abzats:
Kak shablonnyy konstruktor: podstavil polya - i u tebya akkuratnyy document i pismo dlya otpravki.

# c=a+b"""
from __future__ import annotations
import os, json, time, hashlib, html, re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
CUR=os.getenv("CUR","EUR")
OUT=os.getenv("OUT_PROPOSALS","data/outreach/proposals")

def _ensure():
    os.makedirs(OUT, exist_ok=True)

def _read_opps()->list[dict]:
    DB=os.getenv("OPPS_DB","data/opps/opps.jsonl")
    if not os.path.isfile(DB): return []
    out=[]
    with open(DB,"r",encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if not ln: continue
            try: out.append(json.loads(ln))
            except Exception: pass
    # svernem po id k posledney versii
    seen=set(); uniq=[]
    for it in reversed(out):
        if it.get("id") in seen: continue
        seen.add(it.get("id")); uniq.append(it)
    return list(reversed(uniq))

def _get_opp(oid: str)->dict|None:
    for it in _read_opps():
        if it.get("id")==oid: return it
    return None

def _pay_instructions()->str:
    parts=[]
    if os.getenv("DAD_IBAN",""): parts.append(f"IBAN: {os.getenv('DAD_IBAN')}")
    if os.getenv("DAD_BIC",""): parts.append(f"BIC: {os.getenv('DAD_BIC')}")
    if os.getenv("DAD_PAYPAL",""): parts.append(f"PayPal: {os.getenv('DAD_PAYPAL')}")
    if os.getenv("DAD_USDT",""): parts.append(f"USDT: {os.getenv('DAD_USDT')}")
    parts.append(f"Beneficiary: {os.getenv('DAD_NAME','Owner')} · Email: {os.getenv('DAD_EMAIL','owner@example.org')}")
    return " | ".join(parts)

def _md(opp: dict, extras: dict)->str:
    skills=", ".join(opp.get("skills") or [])
    tone=extras.get("tone","neutral")
    portfolio="/portfolio/view"
    title=opp.get("title","Proposal")
    budget=opp.get("budget",0.0); currency=opp.get("currency",CUR)
    md=f"""# Proposal — {title}

**From:** Ester (on behalf of {os.getenv('DAD_NAME','Owner')})  
**To:** {opp.get('source','Client')}  
**Date:** {time.strftime('%Y-%m-%d')}  

## Scope & Fit
- Problem: implement requested solution efficiently (RAG/LLM/Automation).
- Why us: proven pipelines (media ingest, RAG, cron, P2P, dashboard, invoices), A/B-safe, drop-in.
- Skills: {skills or 'N/A'}.

## Deliverables
1) Working module(s) as drop-in files, with REST and actions.  
2) Minimal dashboard and logs (passport).  
3) Optional: docs (MD/HTML), tests/smoke and portfolio entry.

## Timeline & Budget
- Start: immediately after confirmation.  
- ETA: negotiated per scope; milestones weekly.  
- Budget: ~{budget:.0f} {currency} (subject to scope).  

## Payment
...  
- Site/Portfolio: {portfolio}

_Tone: {tone}_.
"""
    return md

def _to_html(md: str)->str:
    # prosteyshiy MD→HTML (tot zhe podkhod, chto v invoice)
    import re, html as _h
    h=_h.escape(md)
    h=re.sub(r"^# (.+)$", r"<h1>\1</h1>", h, flags=re.M)
    h=re.sub(r"^## (.+)$", r"<h2>\1</h2>", h, flags=re.M)
    h=re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", h)
    h=h.replace("\n\n", "<br><br>")
    return f"<!doctype html><meta charset='utf-8'><body style='font-family:system-ui;padding:20px'>{h}</body>"

def _email(opp: dict, md: str)->str:
    subj=f"Proposal: {opp.get('title','Solution')} — Ester"
    # Bez backslash v f-stroke: gotovim host otdelno i bezopasno
    raw_url = opp.get("url", "example.com")
    host = re.sub(r"^.*://(www\.)?", "", raw_url).split("/")[0]
    if not host:
        host = "example.com"
    to_addr = f"contact@{host}"
    to = ", ".join(opp.get("emails", []) or [to_addr])
    body=f"{subj}\n\nHello,\n\nPlease find the proposal attached (or linked).\n\nSummary:\n- Approach: RAG/LLM/Automation, drop-in.\n- Budget: ~{opp.get('budget',0)} {opp.get('currency',CUR)}.\n- Payment: {_pay_instructions()}.\n\nBest regards,\nEster\n"
    return f"TO: {to}\nSUBJECT: {subj}\n\n{body}"

def generate(opp_id: str, extras: dict|None=None)->dict:
    opp=_get_opp(opp_id)
    if not opp: return {"ok": False, "error":"opp_not_found"}
    _ensure()
    md=_md(opp, extras or {})
    html=_to_html(md)
    base=os.path.join(OUT, opp_id)
    mdp=base+".md"; htmlp=base+".html"; mailp=base+".email.txt"
    open(mdp,"w",encoding="utf-8").write(md)
    open(htmlp,"w",encoding="utf-8").write(html)
    open(mailp,"w",encoding="utf-8").write(_email(opp, md))
    # profile + RAG
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        from modules.media.utils import rag_append  # type: ignore
        _pp("outreach_generate", {"opp_id": opp_id}, "ops://outreach")
        rag_append(f"proposal-{opp_id}", md)
    except Exception:
        pass
    return {"ok": True, "id": opp_id, "paths": {"md": mdp, "html": htmlp, "email": mailp}}

def get_path(opp_id: str, fmt: str="md")->dict:
    base=os.path.join(OUT, opp_id)
    path = base + (".html" if fmt=="html" else (".email.txt" if fmt=="email" else ".md"))
    if not os.path.isfile(path):
        return {"ok": False, "error":"not_found"}
    return {"ok": True, "path": path}
# c=a+b
