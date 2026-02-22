# -*- coding: utf-8 -*-
"""
modules/finance/invoice.py — oflayn-scheta: Markdown/HTML iz JSON, bez vneshnikh servisov.

Mosty:
- Yavnyy: (Frilans ↔ Dokumenty) bystro vypuskat scheta i prikladyvat k otklikam.
- Skrytyy #1: (Profile ↔ Prozrachnost) kazhdyy schet shtampuetsya.
- Skrytyy #2: (RAG ↔ Poisk) tekst scheta kladem v gibridnyy poisk.

Zemnoy abzats:
Eto kak blank-kvitantsiya v yaschike: zapolnil polya — poluchil akkuratnyy schet, kotoryy mozhno otpravit.

# c=a+b
"""
from __future__ import annotations
import os, json, time, hashlib
from typing import Any, Dict, List
from modules.media.utils import passport, rag_append
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DIR=os.getenv("INVOICE_DIR","data/invoices")
CUR=os.getenv("INVOICE_CURRENCY","EUR")

def _ensure():
    os.makedirs(DIR, exist_ok=True)

def _id(data: dict)->str:
    s=json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def _fmt_money(x: float)->str:
    return f"{x:,.2f} {CUR}".replace(",", " ")

def _render_md(d: dict, iid: str, total: float, vat: float, grand: float)->str:
    lines=[]
    lines+= [f"# Invoice {iid}", ""]
    lines+= [f"**Issuer:** {d.get('issuer',{}).get('name','')}, {d.get('issuer',{}).get('email','')}"]
    lines+= [f"**Client:** {d.get('client',{}).get('name','')}, {d.get('client',{}).get('email','')}", ""]
    lines+= ["| # | Description | Qty | Price | Sum |", "|---|-------------|-----|-------|-----|"]
    for i,it in enumerate(d.get("items") or [], start=1):
        sum_=float(it.get("qty",0))*float(it.get("price",0))
        lines+= [f"| {i} | {it.get('desc','')} | {it.get('qty',0)} | {_fmt_money(float(it.get('price',0)))} | {_fmt_money(sum_)} |"]
    lines+= ["", f"**Subtotal:** {_fmt_money(total)}  ", f"**VAT:** {_fmt_money(vat)}  ", f"**Total:** **{_fmt_money(grand)}**  ", ""]
    if d.get("meta"): lines+= [f"_Meta_: {json.dumps(d['meta'], ensure_ascii=False)}", ""]
    lines+= [f"_Issue time:_ {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"]
    return "\n".join(lines)

def _render_html(md: str)->str:
    # minimalistichnyy Markdown→HTML (tolko nash format)
    import html, re
    h=html.escape(md)
    # zagolovok
    h=re.sub(r"^# (.+)$", r"<h1>\1</h1>", h, flags=re.M)
    # zhirnyy
    h=re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", h)
    # kursiv
    h=re.sub(r"_(.+?)_", r"<em>\1</em>", h)
    # tablitsa (naivno)
    h=h.replace("| ---", "|---")
    h=h.replace("\n|", "\n<tr><td>").replace("|", "</td><td>").replace("\n", "</td></tr>\n")
    # zavernem
    return f"<!doctype html><meta charset='utf-8'><style>body{{font-family:system-ui;padding:20px}} table,td{{border:1px solid #ddd;border-collapse:collapse}} td{{padding:6px 8px}}</style><body>{h}</body>"

def create(data: dict)->dict:
    _ensure()
    items=data.get("items") or []
    subtotal=sum(float(x.get("qty",0))*float(x.get("price",0)) for x in items)
    vat=float(data.get("vat_rate",0.0))*subtotal
    grand=subtotal+vat
    iid=_id({"items": items, "client": data.get("client"), "issuer": data.get("issuer"), "ts": int(time.time())})
    md=_render_md(data, iid, subtotal, vat, grand)
    html=_render_html(md)

    pfx=os.path.join(DIR, iid)
    mdp=pfx+".md"; htmlp=pfx+".html"
    open(mdp,"w",encoding="utf-8").write(md)
    open(htmlp,"w",encoding="utf-8").write(html)

    # profilea i RAG
    passport("invoice_create", {"id": iid, "subtotal": subtotal, "vat": vat, "grand": grand}, "finance://invoice")
    rag_append(f"invoice-{iid}", md)

    return {"ok": True, "id": iid, "paths": {"md": mdp, "html": htmlp}, "subtotal": subtotal, "vat": vat, "total": grand}

def get(iid: str, kind: str="md")->dict:
    path=os.path.join(DIR, f"{iid}.{('html' if kind=='html' else 'md')}")
    if not os.path.isfile(path):
        return {"ok": False, "error":"not_found"}
    return {"ok": True, "path": path}
# c=a+b