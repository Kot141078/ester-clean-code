# -*- coding: utf-8 -*-
from __future__ import annotations
"""Drop-in: added RAG Eval link to mini-UI reports."""
import os, html
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PREFIX = os.getenv("ESTER_REPORTS_PREFIX", "/compat/reports")
AB = os.getenv("ESTER_UI_AB","A").upper().strip() or "A"

_LINKS = [
    ("System",  "system.md",   "System summary (folders/progress)"),
    ("RAG",     "rag.md",      "Indeks RAG (sostoyanie i primery)"),
    ("RAG Feedback", "rag_feedback.md", "Log of answers and sources"),
    ("RAG Eval", "rag_eval.md", "Offlayn-otsenka RAG"),
    ("Metrics", "metrics.md",  "Kachestvo: okno, p90, error-rate"),
    ("Routes",  "routes.md",   "Marshruty i kollizii"),
    ("Selfcheck (md)", "selfcheck/summary.md", "Samoproverka (markdown)"),
    ("Selfcheck (json)", "selfcheck/detail.json", "Samoproverka (podrobno)"),
    ("KG snapshot", "kg/snapshot.json", "Graf znaniy (snimok)"),
]

_HTML_HEAD = """<!doctype html>
<html lang="ru">
<meta charset="utf-8">
<title>Ester — Reports</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root { --bg:#0b1220; --fg:#e6eefc; --muted:#a6b0c0; --card:#121a2b; --accent:#7cc3ff; }
html,body { margin:0; padding:0; background:var(--bg); color:var(--fg); font:14px/1.45 system-ui,Segoe UI,Roboto,Arial; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
.container { max-width: 980px; margin: 24px auto; padding: 0 16px; }
.card { background:var(--card); border-radius:16px; padding:16px 18px; box-shadow:0 6px 24px rgba(0,0,0,.25); margin-bottom:16px; }
.h1 { font-size:22px; margin:0 0 12px 0; }
.muted { color:var(--muted); }
.row { display:flex; flex-wrap:wrap; gap:8px 12px; }
.badge { background:#1b2540; border:1px solid #223055; border-radius:999px; padding:6px 10px; }
details { border:1px solid #223055; border-radius:12px; padding:10px 12px; background:#101726; }
summary { cursor:pointer; outline:none; }
pre { white-space:pre-wrap; background:#0e1525; border-radius:12px; padding:12px; overflow:auto; }
.hr { height:1px; background:#203050; margin:10px 0 6px; }
footer { opacity:.7; font-size:12px; margin:16px 0 8px; }
.btn { display:inline-block; padding:10px 14px; border-radius:10px; border:1px solid #223055; background:#1b2540; color:#e6eefc; text-decoration:none; }
.btn:hover { background:#24325a; }
</style>
<div class="container">
  <div class="card">
    <div class="h1">Ester — Reports index</div>
    <div class="muted">/compat/reports/index.html</div>
  </div>
  <div class="card">
    <div class="h1">Ssylki</div>
    <div class="row">
"""

_HTML_TAIL = """
  </div>
  <div class="card">
    <div class="h1">Eksport</div>
    <a class="btn" href="{prefix}/download.tar.gz">Download pack (.tar.gz)</a>
    <span class="badge"><a href="{prefix}/download.json" target="_blank">Manifest</a></span>
  </div>
  <footer class="container muted">c=a+b</footer>
</div>
</html>
"""

def _html() -> str:
    links = "".join(f'<span class="badge"><a href="{_PREFIX}/{path}" target="_blank">{name}</a></span>' for (name, path, _) in _LINKS)
    preview = ""
    if AB == "A":
        preview += '<div class="card"><div class="h1">Predprosmotr</div></div>'
        for i,(name,path,desc) in enumerate(_LINKS):
            preview += f'<details class="card"><summary>{name} - <span class="muted">{html.escape(desc)}</span></summary><div class="hr"></div><pre id="md_{i}">Zagruzka...</pre></details>'
        preview += f"""
<script>
const prefix = {_PREFIX!r};
async function fetchText(url) {{ try {{ const r = await fetch(url); return await r.text(); }} catch(e) {{ return 'Oshibka zagruzki: '+e; }} }}
const links = [{",".join([("{"+f"name:{name!r}, path:{path!r}"+"}") for name,path,_ in _LINKS])}];
links.forEach(async (it, i) => {{
  const el = document.getElementById('md_'+i);
  if (!el) return;
  el.textContent = await fetchText(prefix + '/' + it.path);
}});
</script>"""
    return (_HTML_HEAD + links + _HTML_TAIL.format(prefix=_PREFIX)).replace("</div>\n</html>", "")

def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response
    except Exception:
        return False
    p = (prefix or _PREFIX) + "/index.html"
    @app.get(p, response_class=__import__("fastapi").Response)  # type: ignore
    def _index():
        return Response(content=_html(), media_type="text/html; charset=utf-8")
    return True

def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import Response
    except Exception:
        return False
    p = (prefix or _PREFIX) + "/index.html"
    @app.get(p)
    def _index():
        return Response(_html(), mimetype="text/html")
    return True