# -*- coding: utf-8 -*-
"""modules/thinking/actions_oneclick_green.py - One-Click Green Agent (sborka speka, plana, faylov i otcheta).

Mosty:
- Yavnyy: (Mysli/Deystviya ↔ Kaskad/Memory) — otdaem plan k ispolneniyu i pishem zametku v profile (cherez suschestvuyuschie ruchki).
- Skrytyy #1: (Mysli ↔ Dokumentatsiya/Kodogeneratsiya) — gotovim fayly-prevyu i, pri razreshenii, primenyaem cherez guarded_apply.
- Skrytyy #2: (Mysli ↔ Sustainability Kit/Report) — berem cheklisty/metriki i sobiraem MD/HTML otchet, ne menyaya API.

Zemnoy abzats:
Odna komanda dlya Ester: iz tseli - srazu rabochiy komplekt (opisanie agenta, plan, fayly, checklist/metriki i otchet). Po umolchaniyu - prevyu; zapis vklyuchaetsya yavnym flagom.
# c=a+b."""
from __future__ import annotations
import os, re, time, json, io
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_SLOT = (os.getenv("ESTER_AGENT_BUILDER_AB","A") or "A").upper()
ALLOW_WRITE = bool(int(os.getenv("ESTER_AGENT_BUILDER_WRITE","0")))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS_DIR = os.path.join(ROOT, "docs")
AGENTS_DIR = os.path.join(DOCS_DIR, "agents")
KIT_DIR = os.path.join(DOCS_DIR, "sustainability_kit")
CHECK_DIR = os.path.join(KIT_DIR, "checklists")
METRICS_JSON = os.path.join(KIT_DIR, "metrics.json")
TEMPL_DIR = os.path.join(ROOT, "examples", "plans")

def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9a-yaA-Ya_-]+", "_", (s or "").strip())
    return s.strip("_") or "agent"

def _read_text(path: str) -> str:
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()

def _read_json(path: str):
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _mk_spec(goal: str, audience: str, domain: str, name: str | None = None) -> Dict[str, Any]:
    ng = (goal or "").strip()
    nm = name or ("EkoRazum" if ("sustain" in (domain or "").lower() or "eko" in ng.lower()) else "Generalist-Agent")
    return {
        "name": nm,
        "description": f"Agent for target: ZZF0Z; audience: ZZF1ZZ; domain: ZZF2ZZ.",
        "instructions": "Be helpful, strictly factual, explain briefly, suggest next steps.",
        "capabilities": ["web.browse","files.analyze","plans.cascade","rules.policy.hints"]
    }

def _mk_plan(goal: str) -> Dict[str, Any]:
    return {
        "ok": True,
        "goal": goal or "sobrat agenta",
        "steps": [
            {"kind":"reflect.enqueue","endpoint":"/thinking/reflection/enqueue","body":{"item":{"text":goal,"meta":{"importance":0.6}}}},
            {"kind":"mem.passport.append","endpoint":"/thinking/act","body":{"name":"mem.passport.append","args":{"note":f"ONECLICK: plan sozdan ({goal})","meta":{"from":"actions_oneclick_green"},"source":"thinking://oneclick.green"}}},
            {"kind":"self.map","endpoint":"/thinking/act","body":{"name":"self.map","args":{}}}
        ],
        "ab": AB_SLOT
    }

def _mk_files(spec: Dict[str, Any]) -> List[Dict[str, str]]:
    """We are trying to reuse the file generator from actions_build_agent_helper;
    if there is no import, we make a safe falsification."""
    files: List[Dict[str, str]] = []
    try:
        from modules.thinking.actions_build_agent_helper import _make_files_for  # type: ignore
        return _make_files_for(spec)
    except Exception:
        # false: agent documentation + auto-plan (ZHSION-v-*.yaml for compatibility)
        name = spec.get("name") or "Agent"
        slug = _slug(name)
        desc = spec.get("description") or ""
        instr = spec.get("instructions") or ""
        caps  = spec.get("capabilities") or []
        files.append({
            "path": f"docs/agents/{slug}.md",
            "content": f"# ZZF0Z\n\nZZF1ZZ\n\n## Instructions\n\nZZF2ZZ\n\n## Features\n\n-" + "\n- ".join(map(str, caps)) + "\n"
        })
        plan = _mk_plan(f"Sobrat agenta «{name}»")
        files.append({
            "path": f"examples/plans/agent_{slug}_auto.yaml",
            "content": json.dumps(plan, ensure_ascii=False, indent=2)
        })
        return files

def _kit(check_id: str = "smb_quick_audit") -> Dict[str, Any]:
    data = {"checklist_id": check_id, "checklist_md":"", "metrics":{}}
    try:
        p = os.path.join(CHECK_DIR, f"{check_id}.md")
        if os.path.isfile(p): data["checklist_md"] = _read_text(p)
    except Exception:
        pass
    try:
        if os.path.isfile(METRICS_JSON): data["metrics"] = _read_json(METRICS_JSON)
    except Exception:
        pass
    return data

def _md(title: str, goal: str, brief: Dict[str,Any], checklist_md: str, metrics: Dict[str,Any]) -> str:
    try:
        from modules.thinking.actions_report_export import _compose_md  # type: ignore
        return _compose_md(title, goal, brief, checklist_md, metrics)
    except Exception:
        outline = brief.get("outline") if isinstance(brief, dict) else []
        ol = "\n".join([f"- {x}" for x in (outline or [])]) or "- —"
        return f"# {title}\n\n**Tsel:** {goal}\n\n## Kratkiy brif\n{ol}\n\n## Vybrannye praktiki\n{checklist_md or '_net dannykh_'}\n"

def _html(title: str, md_text: str) -> str:
    try:
        from modules.thinking.actions_report_export import _compose_html  # type: ignore
        return _compose_html(title, md_text)
    except Exception:
        return f"<!doctype html><meta charset='utf-8'><title>{title}</title><pre>{md_text}</pre>"

def _guarded_apply(files: List[Dict[str,str]]) -> Dict[str,Any]:
    try:
        from modules.self.codegen import test_files, guarded_apply  # type: ignore
        test_rep = test_files(files, "")
        if (AB_SLOT!="A") or (not ALLOW_WRITE):
            return {"ok": bool(test_rep.get("ok", True)), "preview": True, "test": test_rep, "ab": AB_SLOT}
        app = guarded_apply(files)
        return {"ok": bool(app.get("ok", False)), "preview": False, "apply": app, "ab": AB_SLOT}
    except Exception as e:
        return {"ok": False, "error": f"codesmith:{e}", "preview": True, "ab": AB_SLOT}

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    # 1) oneclick.green.bundle — sobrat vse srazu (bez zapisi)
    def a_bundle(args: Dict[str,Any]):
        goal = str(args.get("goal","") or "")
        audience = str(args.get("audience","") or "")
        domain = str(args.get("domain","any") or "any")
        name = str(args.get("name","") or "")
        spec = _mk_spec(goal, audience, domain, name or None)
        plan = _mk_plan(goal or f"Sobrat agenta «{spec['name']}»")
        files = _mk_files(spec)
        kit = _kit("smb_quick_audit")
        brief = {
            "outline":[
                f"Tsel: {goal or '—'}",
                f"Auditoriya: {audience or '—'}",
                f"Domen: {domain}",
                "Metriki: CO₂e, kWh, otkhody; step: audit → bystraya ekonomiya → struktura → monitoring."
            ],
            "hints":{"checklist": kit["checklist_id"], "metrics_file":"docs/sustainability_kit/metrics.json"}
        }
        title = f"Eco-report: ZZF0Z"
        md = _md(title, goal or title, brief, kit.get("checklist_md",""), kit.get("metrics",{}))
        html = _html(title, md)
        bundle = {"spec":spec, "plan":plan, "files":files, "report":{"title":title, "markdown":md, "html":html}, "ab": AB_SLOT}
        return {"ok": True, "bundle": bundle, "ab": AB_SLOT}
    register("oneclick.green.bundle", {"goal":"str","audience":"str","domain":"str","name":"str"}, {"ok":"bool"}, 1, a_bundle)

    # 2) oneclick.green.apply — primenit bundle.files (guarded_apply)
    def a_apply(args: Dict[str,Any]):
        bundle = dict(args.get("bundle") or {})
        files = list(bundle.get("files") or [])
        if not files:
            return {"ok": False, "error":"no files", "ab": AB_SLOT}
        rep = _guarded_apply(files)
        rep["files"] = files
        return rep
    register("oneclick.green.apply", {"bundle":"object"}, {"ok":"bool"}, 2, a_apply)

_reg()
# c=a+b.