# -*- coding: utf-8 -*-
"""
R5/services/portal/template.py — minimalnyy HTML-shablon staticheskoy stranitsy portala.

Mosty:
- Yavnyy: Enderton — razmetka kak proveryaemaya spetsifikatsiya (determinirovannyy HTML iz JSON).
- Skrytyy #1: Cover & Thomas — myagkaya vizualizatsiya «signala» (summary/tegi) bez lishnego shuma.
- Skrytyy #2: Ashbi — A/B-slot: rezhim B dobavlyaet lentochki tegov i aktsenty; pri oshibkakh — katbek v A.

Zemnoy abzats (inzheneriya):
Vstavlyaem inline-CSS i minimalnyy JS (tolko dlya raskrytiya sektsiy). Nikakikh vneshnikh zavisimostey.
Gotovo dlya lokalnogo otkrytiya fayla v brauzere (file://).

# c=a+b
"""
from __future__ import annotations
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE_CSS = """
*{box-sizing:border-box}body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;margin:2rem;color:#111}
h1{margin:0 0 1rem 0} .meta{color:#555;font-size:.9rem;margin-bottom:1rem}
section{border:1px solid #e3e3e3;border-radius:12px;padding:1rem;margin:0 0 1rem 0;box-shadow:0 1px 2px rgba(0,0,0,.03)}
h2{margin:0 0 .5rem 0;font-size:1.05rem}
.badge{display:inline-block;padding:.15rem .5rem;margin:.12rem;border-radius:999px;background:#f3f3f3;border:1px solid #eee;font-size:.75rem;color:#333}
.item{padding:.25rem 0}
.tags{margin:.25rem 0}
footer{margin-top:2rem;color:#666;font-size:.85rem}
"""

BASE_HTML = """<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta">UTC: {utc} • mode={mode}</div>
{tagbar}
{sections}
# <footer>Sgenerirovano offlayn (R5). c=a+b</footer>
</body></html>"""

def render_tagbar(tag_hist: dict | None) -> str:
    if not tag_hist:
        return ""
    badges = "".join(f'<span class="badge">#{k} — {v}</span>' for k, v in sorted(tag_hist.items()))
    return f'<div class="tags">{badges}</div>'

def render_sections(digest: dict) -> str:
    blocks = []
    for s in digest.get("sections", []):
        tags = s.get("tags") or []
        items_html = "".join(
            f'<div class="item"><strong>{i+1}.</strong> {it.get("summary")} '
            f'<span class="tags">{" ".join(f"<span class=\\"badge\\">#"+t+"</span>" for t in (it.get("tags") or []))}</span></div>'
            for i, it in enumerate(s.get("items", []))
        )
        blocks.append(
            f'<section><h2>{s.get("query")} {" ".join("#"+t for t in tags)}</h2>{items_html}</section>'
        )
    return "\n".join(blocks)

def render_html(digest: dict) -> str:
    tagbar = render_tagbar((digest.get("meta") or {}).get("tag_hist"))
    return BASE_HTML.format(
        title=digest.get("title","Ester Digest"),
        utc=digest.get("generated_utc",""),
        mode=digest.get("mode","A"),
        css=BASE_CSS,
        tagbar=tagbar,
        sections=render_sections(digest),
# )  # Fixed: f-string expression part cannot include a backslash (<unknown>, line 56)