# -*- coding: utf-8 -*-
"""
modules/portfolio/builder.py — statichnoe portfolio: sobiraem kartochki iz Garage/Media/Invoices i renderim HTML.

Mosty:
- Yavnyy: (Garage/Media/Invoices ↔ Vitrina) vse, chto Ester delaet, prevraschaetsya v stranitsu «chto ya umeyu».
- Skrytyy #1: (Profile ↔ Prozrachnost) sborka fiksiruetsya i legko vosproizvoditsya.
- Skrytyy #2: (RAG ↔ Poisk) tot zhe HTML mozhno zataschit v RAG kak referens.

Zemnoy abzats:
Kak vitrina v masterskoy: proekty, roliki i scheta — v akkuratnykh kartochkakh, chtoby otpravit ssylku ili raspechatat.

# c=a+b
"""
from __future__ import annotations
import os, json, time, glob, html
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

OUT_DIR=os.getenv("PORTFOLIO_DIR","data/portfolio")
GARAGE_REG=os.getenv("GARAGE_REG","data/garage/registry.json")
MEDIA_DB=os.getenv("MEDIA_DB","data/media/index.json")
INV_DIR=os.getenv("INVOICE_DIR","data/invoices")

def _read_json(path: str)->dict:
    try:
        return json.load(open(path,"r",encoding="utf-8"))
    except Exception:
        return {}

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "ui://portfolio")
    except Exception:
        pass

def build()->dict:
    os.makedirs(OUT_DIR, exist_ok=True)
    reg=_read_json(GARAGE_REG)
    media=_read_json(MEDIA_DB)
    invoices=sorted(glob.glob(os.path.join(INV_DIR,"*.html")))
    projs=(reg.get("projects") or {})
    items_media=(media.get("items") or [])
    # HTML
    head="""<!doctype html><meta charset="utf-8">
    <title>Ester Portfolio</title>
    <style>
    body{font-family:system-ui;margin:0;background:#fafafa}
    header{padding:16px 20px;background:#111;color:#fff}
    .wrap{padding:20px;}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
    .card{background:#fff;border:1px solid #eee;border-radius:12px;box-shadow:0 2px 6px rgba(0,0,0,0.04);padding:12px}
    .muted{color:#666;font-size:12px}
    a{color:#0b66c3;text-decoration:none}
    </style>"""
    body=["<header><h1>Ester — Portfolio</h1><div class='muted'>Generated: "+time.strftime("%Y-%m-%d %H:%M:%S")+"</div></header><div class='wrap'>"]

    # Projects
    body.append("<h2>Projects</h2><div class='grid'>")
    for name, info in sorted(projs.items(), key=lambda kv: kv[1].get("t",0), reverse=True):
        body.append(f"<div class='card'><h3>{html.escape(name)}</h3><div class='muted'>{html.escape(info.get('module',''))}</div><div>Route base: {html.escape(info.get('route_base',''))}</div></div>")
    body.append("</div>")

    # Media
    body.append("<h2>Media</h2><div class='grid'>")
    for it in items_media[-12:][::-1]:
        mid=it.get("id"); svc=it.get("service","")
        has_notes=bool((it.get("paths") or {}).get("notes"))
        body.append(f"<div class='card'><h3>Media {html.escape(mid or '')}</h3><div class='muted'>service: {html.escape(svc)}</div>")
        body.append(f"<div><a href='/media/video/get?id={html.escape(mid)}'>card</a> · <a href='/media/video/text?id={html.escape(mid)}&type=notes'>notes</a>{' ✅' if has_notes else ''}</div></div>")
    body.append("</div>")

    # Invoices
    body.append("<h2>Invoices</h2><div class='grid'>")
    for p in invoices[-12:][::-1]:
        fn=os.path.basename(p)
        body.append(f"<div class='card'><h3>{html.escape(fn)}</h3><div><a href='/finance/invoice/get?id={html.escape(os.path.splitext(fn)[0])}&format=html'>open</a></div></div>")
    body.append("</div>")

    body.append("</div>")
    html_out=head+"\n<body>\n"+("\n".join(body))+"\n</body>"
    out_path=os.path.join(OUT_DIR,"index.html")
    open(out_path,"w",encoding="utf-8").write(html_out)
    _passport("portfolio_build", {"projects": len(projs), "media": len(items_media), "invoices": len(invoices)})
    return {"ok": True, "path": out_path}

def get_path()->str:
    p=os.path.join(OUT_DIR,"index.html")
    return p if os.path.isfile(p) else ""
# c=a+b