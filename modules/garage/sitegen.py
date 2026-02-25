# -*- coding: utf-8 -*-
"""modules/garage/sitegen.py - prostaya sborka staticheskogo sayta proekta/portfolio.

Mosty:
- Yavnyy: (Documenty ↔ Verstka) prevraschaem dannye proekta v index.html+style.css.
- Skrytyy #1: (Portfolio ↔ Garazh) globalnyy sayt portfolio stroitsya iz registry JSON.
- Skrytyy #2: (Memory ↔ Profile) fakt sborki sokhranyaem v pamyat dlya trassirovki.

Zemnoy abzats:
Nazhali knopku - i na vykhode akkuratnaya statichnaya stranitsa, kotoruyu mozhno otdat zakazchiku.

# c=a+b"""
from __future__ import annotations
import os, json, time, html
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PORTF=os.getenv("GARAGE_PORTFOLIO","data/garage/portfolio.json")

def _passport(note:str, meta:Dict[str,Any])->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="garage://sitegen")
    except Exception:
        pass

STYLE = """
body{font-family:ui-sans-serif,system-ui,Arial;margin:0;background:#0b0f14;color:#e5e7eb}
.wrap{max-width:900px;margin:0 auto;padding:40px}
.card{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:24px;margin:16px 0;box-shadow:0 6px 18px rgba(0,0,0,.25)}
h1{margin:0 0 8px;font-size:28px}
h2{margin:24px 0 8px;font-size:20px}
a, a:visited{color:#93c5fd}
pre{white-space:pre-wrap;background:#0f172a;padding:12px;border-radius:12px;overflow:auto}
small{color:#9ca3af}
"""

def build_project_site(proj: Dict[str,Any], theme:str="clean")->Dict[str,Any]:
    site=os.path.join(proj["path"],"site")
    os.makedirs(site, exist_ok=True)
    # sobrat kontent
    readme=os.path.join(proj["path"],"README.md")
    readme_text=open(readme,"r",encoding="utf-8").read() if os.path.isfile(readme) else ""
    proposal=os.path.join(proj["path"],"docs","proposal.md")
    proposal_text=open(proposal,"r",encoding="utf-8").read() if os.path.isfile(proposal) else ""
    # html
    html_s=f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(proj['name'])}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{STYLE}</style></head><body><div class="wrap">
<div class="card"><h1>{html.escape(proj['name'])}</h1><small>ID: {proj['id']} · {time.strftime("%Y-%m-%d")}</small>
<p>{html.escape(proj.get('brief',''))}</p></div>
<div class="card"><h2>README</h2><pre>{html.escape(readme_text[:4000])}</pre></div>
<div class="card"><h2>Proposal</h2><pre>{html.escape(proposal_text[:8000])}</pre></div>
</div></body></html>"""
    open(os.path.join(site,"index.html"),"w",encoding="utf-8").write(html_s)
    _passport("Sobran mini-sayt proekta", {"project": proj["id"]})
    return {"ok": True, "site_dir": site}

def build_portfolio_site()->Dict[str,Any]:
    os.makedirs(os.path.dirname(PORTF), exist_ok=True)
    data=json.load(open(PORTF,"r",encoding="utf-8")) if os.path.isfile(PORTF) else {"items":[]}
    site="data/garage/portfolio_site"; os.makedirs(site, exist_ok=True)
    items=data.get("items",[])
    rows="".join([f"<div class='card'><h2>{html.escape(x.get('title',''))}</h2><p>{html.escape(x.get('summary',''))}</p><small>{html.escape(x.get('tags',''))}</small></div>" for x in items])
    html_s=f"<!doctype html><html><head><meta charset='utf-8'><title>Ester Portfolio</title><style>{STYLE}</style></head><body><div class='wrap'><h1>Portfolio</h1>{rows}</div></body></html>"
    open(os.path.join(site,"index.html"),"w",encoding="utf-8").write(html_s)
    _passport("Sobran globalnyy sayt portfolio", {"count": len(items)})
    return {"ok": True, "site_dir": site}
# c=a+b