# -*- coding: utf-8 -*-
"""
modules/thinking/actions_report_export.py — sborka i eksport otchetov (MD/HTML) iz znaniy Ester.

Mosty:
- Yavnyy: (Mysli/Deystviya ↔ Dokumentatsiya) — vozvraschaem gotovyy Markdown/HTML i pri razreshenii pishem fayly v docs/reports/.
- Skrytyy #1: (UX ↔ Kaskad) — formiruem mini-plan i sovmestimy s /thinking/cascade/execute (kak v admin_cascade.js).
- Skrytyy #2: (Pravila ↔ Memory) — zapis faylov idet cherez guarded_apply (A-slot + WRITE-flag), sobytiya mozhno logirovat v profile.

Zemnoy abzats:
Ester poluchaet «knopku» sobrat otchet pod tsel (tseli, cheklisty, metriki), prevyu v MD/HTML i, esli razresheno, zapis gotovykh artefaktov ryadom s dokumentatsiey — bez izmeneniya API.
# c=a+b.
"""
from __future__ import annotations
import os, re, time, json
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_SLOT = (os.getenv("ESTER_AGENT_BUILDER_AB","A") or "A").upper()
ALLOW_WRITE = bool(int(os.getenv("ESTER_AGENT_BUILDER_WRITE","0")))
REPORTS_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "docs", "reports")
TEMPLATE_PATH = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")), "docs", "report_template.html")

def _slug(s: str) -> str:
    t = re.sub(r"[^a-zA-Z0-9a-yaA-Ya_-]+", "_", (s or "report").strip())
    return t.strip("_") or "report"

def _ensure_dirs():
    os.makedirs(REPORTS_DIR, exist_ok=True)

def _compose_md(title: str, goal: str, brief: Dict[str, Any], checklist_md: str, metrics: Dict[str, Any]) -> str:
    outline = brief.get("outline") if isinstance(brief, dict) else None
    ol = ""
    if outline and isinstance(outline, list):
        ol = "\n".join([f"- {x}" for x in outline])
    met = ""
    if isinstance(metrics, dict):
        try:
            units = metrics.get("units","")
            e = metrics.get("electricity",{}).get("grid_generic_kg_per_kwh", "")
            met = f"\n> Metriki (ed.): {units}; Setka (kVt·ch→kgCO₂e): {e}"
        except Exception:
            pass
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    md = f"""# {title}

**Tsel:** {goal}

## Kratkiy brif
{ol or "- —"}

## Vybrannye praktiki (cheklist)
{checklist_md.strip() if checklist_md else "_net dannykh_"}

## Metriki/faktory
{met or "_net dannykh_"}

---

_Sobrano Ester: {now}._
"""
    return md

def _compose_html(title: str, md_text: str) -> str:
    # Bez storonnikh zavisimostey: upakovyvaem Markdown kak pre i dobavlyaem legkie stili
    try:
        tpl = ""
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            tpl = f.read()
    except Exception:
        tpl = """<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>body{font:14px/1.6 system-ui,Segoe UI,Roboto,sans-serif;padding:24px;background:#0b0c10;color:#e5e7eb;}
pre{white-space:pre-wrap;word-break:break-word;border:1px solid #374151;border-radius:8px;padding:12px;background:#0f1115;}
h1{color:#93c5fd}</style></head><body><h1>{title}</h1><pre>{content}</pre></body></html>"""
    html = tpl.replace("{{TITLE}}", title).replace("{{CONTENT_PRE}}", md_text)
    return html

def _safe_register():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return None
    return register

def _guarded_apply(files: List[Dict[str, str]]) -> Dict[str, Any]:
    try:
        from modules.self.codegen import test_files, guarded_apply  # type: ignore
        test_rep = test_files(files, "")
        if (AB_SLOT != "A") or (not ALLOW_WRITE):
            return {"ok": bool(test_rep.get("ok", True)), "preview": True, "test": test_rep, "ab": AB_SLOT}
        app_rep = guarded_apply(files)
        return {"ok": bool(app_rep.get("ok", False)), "preview": False, "apply": app_rep, "ab": AB_SLOT}
    except Exception as e:
        return {"ok": False, "error": f"codesmith:{e}", "preview": True, "ab": AB_SLOT}

def _reg():
    register = _safe_register()
    if not register:
        return

    # 1) report.compose.md — sobrat Markdown iz brifa/cheklista/metrik
    def a_md(args: Dict[str, Any]):
        title = str(args.get("title") or "Otchet po tseli")
        goal  = str(args.get("goal")  or "")
        brief = args.get("brief") or {}
        checklist_md = str(args.get("checklist_md") or "")
        metrics = args.get("metrics") or {}
        md = _compose_md(title, goal, brief, checklist_md, metrics)
        return {"ok": True, "ab": AB_SLOT, "markdown": md}
    register("report.compose.md", {"title":"str","goal":"str","brief":"object","checklist_md":"str","metrics":"object"}, {"ok":"bool"}, 1, a_md)

    # 2) report.compose.html — sobrat HTML-stranitsu (print-to-PDF cherez brauzer)
    def a_html(args: Dict[str, Any]):
        title = str(args.get("title") or "Otchet")
        markdown = str(args.get("markdown") or "")
        html = _compose_html(title, markdown)
        return {"ok": True, "ab": AB_SLOT, "html": html}
    register("report.compose.html", {"title":"str","markdown":"str"}, {"ok":"bool"}, 2, a_html)

    # 3) report.save.files — sokhranit MD/HTML (guarded_apply)
    def a_save(args: Dict[str, Any]):
        title = str(args.get("title") or "report")
        markdown = str(args.get("markdown") or "")
        html = str(args.get("html") or "")
        slug = _slug(title)
        _ensure_dirs()
        files = []
        if markdown:
            files.append({"path": f"docs/reports/{slug}.md", "content": markdown})
        if html:
            files.append({"path": f"docs/reports/{slug}.html", "content": html})
        rep = _guarded_apply(files)
        rep["files"] = files
        return rep
    register("report.save.files", {"title":"str","markdown":"str","html":"str"}, {"ok":"bool"}, 3, a_save)

    # 4) report.plan.quick — otdat mini-plan (sovmestim s /thinking/cascade/execute)
    def a_plan(args: Dict[str, Any]):
        goal = str(args.get("goal") or "sobrat korotkiy otchet")
        plan = {
            "ok": True,
            "goal": goal,
            "steps": [
                {"kind":"reflect.enqueue", "endpoint":"/thinking/reflection/enqueue", "body":{"item":{"text":goal, "meta":{"importance":0.6}}}},
                {"kind":"mem.passport.append", "endpoint":"/thinking/act", "body":{"name":"mem.passport.append","args":{"note":f"REPORT: plan sformirovan ({goal})","meta":{"from":"actions_report_export"},"source":"thinking://report"}}}
            ],
            "ab": AB_SLOT
        }
        return {"ok": True, "plan": plan, "ab": AB_SLOT}
    register("report.plan.quick", {"goal":"str"}, {"ok":"bool"}, 4, a_plan)

_reg()
# c=a+b.