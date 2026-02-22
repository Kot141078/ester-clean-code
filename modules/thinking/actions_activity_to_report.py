# -*- coding: utf-8 -*-
"""
modules/thinking/actions_activity_to_report.py — avtosvertka «aktivnost → otchet».

Mosty:
- Yavnyy: (Mysli/Deystviya ↔ Dokumentatsiya) — formiruem Markdown/HTML otchet na osnove sobytiy aktivnosti.
- Skrytyy #1: (UX ↔ Kaskad) — otdaem mini-plan, sovmestimyy s /thinking/cascade/execute (kak v admin_cascade.js).
- Skrytyy #2: (Pravila ↔ Memory) — sokhranenie faylov cherez guarded_apply (A-slot + WRITE-flag), bez izmeneniya kontraktov.

Zemnoy abzats:
Ester odnim deystviem sobiraet otchet iz poslednikh deystviy (Builder/KIT/Report): sobytiya → kratkaya svodka → MD/HTML → (po razresheniyu) sokhranenie.
# c=a+b.
"""
from __future__ import annotations
import os, io, re, json, time
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_SLOT = (os.getenv("ESTER_AGENT_BUILDER_AB","A") or "A").upper()
ALLOW_WRITE = bool(int(os.getenv("ESTER_AGENT_BUILDER_WRITE","0")))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(ROOT, "data")
SM_STORE = os.path.join(DATA_DIR, "structured_mem", "store.json")
ESTER_MEM = os.path.join(DATA_DIR, "ester_memory.json")
REPORTS_DIR = os.path.join(ROOT, "docs", "reports")
TEMPLATE_PATH = os.path.join(ROOT, "docs", "report_template.html")

PATTERNS = [
    r"AgentBuilder", r"thinking://agent\.builder",
    r"\bKIT:\b", r"\bREPORT:\b",
    r"actions_build_agent_helper", r"admin_agent_kit", r"actions_report_export"
]

def _safe_register():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return None
    return register

def _read_json(path: str) -> Any:
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _iter_candidates() -> List[Any]:
    items = []
    for p in (SM_STORE, ESTER_MEM):
        obj = _read_json(p)
        if obj is not None:
            items.append(obj)
    return items

def _extract_events(obj: Any, q: str | None = None) -> List[Dict[str, Any]]:
    q = (q or "").strip()
    rx = [re.compile(p, re.I) for p in PATTERNS]
    evs: List[Dict[str, Any]] = []
    def walk(x: Any):
        try:
            if isinstance(x, dict):
                note = str(x.get("note") or x.get("text") or "")
                src  = str(x.get("source") or x.get("from") or x.get("origin") or "")
                ts   = x.get("ts") or x.get("time") or x.get("timestamp")
                if any(r.search(note) for r in rx) or any(r.search(src) for r in rx):
                    full = json.dumps(x, ensure_ascii=False)
                    if not q or (q.lower() in full.lower()):
                        evs.append({"ts": int(ts or 0), "source": src or "mem", "note": note[:800]})
                for v in x.values(): walk(v)
            elif isinstance(x, list):
                for v in x: walk(v)
        except Exception:
            return
    walk(obj)
    evs.sort(key=lambda e: int(e.get("ts") or 0), reverse=True)
    # normalizuem ts ako net vremeni
    now = int(time.time())
    for i,e in enumerate(evs):
        if not e.get("ts"):
            e["ts"] = now - i
    return evs

def _scan(q: str, limit: int) -> List[Dict[str,Any]]:
    all_evs: List[Dict[str,Any]] = []
    for obj in _iter_candidates():
        all_evs.extend(_extract_events(obj, q=q))
    if limit > 0:
        all_evs = all_evs[:limit]
    return all_evs

def _compose_md_from_events(title: str, events: List[Dict[str,Any]]) -> str:
    lines = [f"# {title}", "", "## Khronologiya (poslednie sobytiya)"]
    for e in events:
        ts = e.get("ts", 0)
        ts_s = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ts)))
        note = (e.get("note") or "").replace("\n"," ").strip()
        src  = e.get("source") or ""
        lines.append(f"- {ts_s} — {note} _(src: {src})_")
    if not events:
        lines.append("- net sobytiy po filtru")
    lines += ["", "## Sleduyuschie shagi", "- Utochnit tseli i metriki (CO₂e, kWh, otkhody).", "- Sformirovat detalnyy plan kaskada.", "- Pri neobkhodimosti — primenit izmeneniya cherez RuleHub (A-slot + WRITE=1).", "", f"_Sobrano Ester: {time.strftime('%Y-%m-%d %H:%M:%S')}._"]
    return "\n".join(lines)

def _compose_html(title: str, md_text: str) -> str:
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            tpl = f.read()
    except Exception:
        tpl = """<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>body{font:14px/1.6 system-ui,Segoe UI,Roboto,sans-serif;padding:24px;background:#0b0c10;color:#e5e7eb}
pre{white-space:pre-wrap;word-break:break-word;border:1px solid #374151;border-radius:8px;padding:12px;background:#0f1115}</style></head>
<body><h1>{title}</h1><pre>{content}</pre></body></html>"""
        return tpl.format(title=title, content=md_text)
    return tpl.replace("{{TITLE}}", title).replace("{{CONTENT_PRE}}", md_text)

def _guarded_apply(files: List[Dict[str,str]]) -> Dict[str,Any]:
    try:
        from modules.self.codegen import test_files, guarded_apply  # type: ignore
        test_rep = test_files(files, "")
        if (AB_SLOT != "A") or (not ALLOW_WRITE):
            return {"ok": bool(test_rep.get("ok", True)), "preview": True, "test": test_rep, "ab": AB_SLOT}
        rep = guarded_apply(files)
        return {"ok": bool(rep.get("ok", False)), "preview": False, "apply": rep, "ab": AB_SLOT}
    except Exception as e:
        return {"ok": False, "error": f"codesmith:{e}", "preview": True, "ab": AB_SLOT}

def _safe_register_report_compose_html(markdown: str, title: str) -> Dict[str,Any]:
    """
    Ispolzuem uzhe dobavlennuyu logiku report.compose.html, esli dostupna;
    inache — lokalnaya obertka.
    """
    try:
        # probuem vyzvat cherez vnutrenniy modul napryamuyu
        from modules.thinking.actions_report_export import _compose_html as compose_html  # type: ignore
        html = compose_html(title, markdown)
        return {"ok": True, "html": html}
    except Exception:
        html = _compose_html(title, markdown)
        return {"ok": True, "html": html}

def _reg():
    register = _safe_register()
    if not register:
        return

    # 1) activity.report.compose.md — sobrat MD iz sobytiy
    def a_md(args: Dict[str,Any]):
        title = str(args.get("title") or "Otchet aktivnosti Ester")
        q = str(args.get("q","") or "")
        limit = int(args.get("limit", 50))
        evs = _scan(q=q, limit=limit)
        md = _compose_md_from_events(title, evs)
        return {"ok": True, "ab": AB_SLOT, "markdown": md, "count": len(evs)}
    register("activity.report.compose.md", {"title":"str","q":"str","limit":"int"}, {"ok":"bool"}, 1, a_md)

    # 2) activity.report.compose.html — zavernut MD v HTML (ispolzuya report.compose.html pri nalichii)
    def a_html(args: Dict[str,Any]):
        title = str(args.get("title") or "Otchet aktivnosti Ester")
        markdown = str(args.get("markdown") or "")
        rep = _safe_register_report_compose_html(markdown, title)
        return {"ok": True, "ab": AB_SLOT, "html": rep.get("html","")}
    register("activity.report.compose.html", {"title":"str","markdown":"str"}, {"ok":"bool"}, 2, a_html)

    # 3) activity.report.save — sokhranit fayly (guarded_apply)
    def a_save(args: Dict[str,Any]):
        title = str(args.get("title") or "Otchet aktivnosti Ester")
        markdown = str(args.get("markdown") or "")
        html = str(args.get("html") or "")
        slug = re.sub(r"[^a-zA-Z0-9a-yaA-Ya_-]+", "_", title).strip("_") or "report"
        files = []
        if markdown: files.append({"path": f"docs/reports/{slug}.md", "content": markdown})
        if html:     files.append({"path": f"docs/reports/{slug}.html", "content": html})
        rep = _guarded_apply(files)
        rep["files"] = files
        return rep
    register("activity.report.save", {"title":"str","markdown":"str","html":"str"}, {"ok":"bool"}, 3, a_save)

    # 4) activity.report.plan.quick — mini-plan dlya svertki (sovmestim s /thinking/cascade/execute)
    def a_plan(args: Dict[str,Any]):
        title = str(args.get("title") or "Sobrat otchet iz aktivnosti")
        plan = {
            "ok": True,
            "goal": title,
            "steps": [
                {"kind":"reflect.enqueue","endpoint":"/thinking/reflection/enqueue","body":{"item":{"text":title,"meta":{"importance":0.5}}}},
                {"kind":"mem.passport.append","endpoint":"/thinking/act","body":{"name":"mem.passport.append","args":{"note":"ACTIVITY→REPORT: start","meta":{"from":"actions_activity_to_report"},"source":"thinking://activity.report"}}}
            ],
            "ab": AB_SLOT
        }
        return {"ok": True, "ab": AB_SLOT, "plan": plan}
    register("activity.report.plan.quick", {"title":"str"}, {"ok":"bool"}, 4, a_plan)

_reg()
# c=a+b.