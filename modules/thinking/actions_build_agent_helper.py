# -*- coding: utf-8 -*-
"""modules/thinking/actions_build_agent_helper.py - eksheny "voli" dlya vnutrennego Agent Builder.

Mosty:
- Yavnyy: (Mysli ↔ Kaskad/Memory) planiruem shagi cherez kaskad i pishem zametku v Profile.
- Skrytyy #1: (Mysli ↔ Kodogeneratsiya) gotovim spisok faylov i daem optsiyu guarded_apply cherez Codesmith.
- Skrytyy #2: (UX ↔ Adminka) plan kompakten i sovmestim s /thinking/cascade/* (knopki v admin_cascade.js).

Zemnoy abzats:
Nabor “knopok” dlya Ester: opisat agenta, pokazat shablon plana, sobrat kaskad pod tsel i, pri razreshenii, primenit fayly.
# c=a+b."""
from __future__ import annotations
import os, glob, json, time, re
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_SLOT = (os.getenv("ESTER_AGENT_BUILDER_AB","A") or "A").upper()
ALLOW_WRITE = bool(int(os.getenv("ESTER_AGENT_BUILDER_WRITE","0")))
TEMPL_DIR = os.getenv("AB_TEMPLATES_DIR","examples/plans")
DEFAULT_PLAN = "agent_builder_plan.yaml"

def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", (name or "agent").strip())
    return s.strip("_") or "agent"

def _templates_list() -> List[str]:
    os.makedirs(TEMPL_DIR, exist_ok=True)
    pats = [
        os.path.join(TEMPL_DIR, DEFAULT_PLAN),
        os.path.join(TEMPL_DIR, "*agent*plan*.yaml"),
        os.path.join(TEMPL_DIR, "*builder*plan*.yaml"),
    ]
    found: List[str] = []
    for p in pats:
        for x in glob.glob(p):
            if os.path.isfile(x) and x not in found:
                found.append(x)
    return found

def _plan_skeleton(goal: str, note: str | None = None) -> Dict[str, Any]:
    goal = (goal or "").strip() or "collect default agent"
    steps: List[Dict[str, Any]] = []

    # 1) Light reflection - as in the standard cascade
    steps.append({
        "kind":"reflect.enqueue",
        "endpoint":"/thinking/reflection/enqueue",
        "body":{"item":{"text":goal, "meta":{"importance":0.7}}}
    })

    # 2) Profile: zafiksirovat namerenie
    steps.append({
        "kind":"mem.passport.append",
        "endpoint":"/thinking/act",
        "body":{"name":"mem.passport.append",
                "args":{"note": f"AgentBuilder: plan sozdan ({goal})",
                        "meta":{"from":"actions_build_agent_helper","note":str(note or "")},
                        "source":"thinking://agent.builder", "version":"1"}}
    })

    # 3) (Optional) A short “self-map” shot for reference
    steps.append({
        "kind":"self.map",
        "endpoint":"/thinking/act",
        "body":{"name":"self.map","args":{}}
    })

    return {"ok": True, "goal": goal, "steps": steps, "ab": AB_SLOT}

def _make_files_for(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Podgotovit bezopasnyy nabor faylov (preview-first)."""
    now = int(time.time())
    name = str(spec.get("name") or "Agent")
    slug = _slug(name)
    desc = str(spec.get("description") or "")
    instr = str(spec.get("instructions") or "")
    caps  = list(spec.get("capabilities") or [])

    files: List[Dict[str, Any]] = []
    # 1) Doc with agent instructions
    files.append({
        "path": f"docs/agents/{slug}.md",
        "content": f"# ZZF0Z\n\nZZF1ZZ\n\n## Instructions\n\nZZF2ZZ\n\n## Features\n\n-" + "\n- ".join(map(str, caps)) + "\n"
    })
    # 2) An example of a cascade plan for launching it
    plan = {
        "run_id": f"agent_{slug}_{now}",
        "branch_id": "main",
        "context_init": {
            "spec": f"Sobrat i primenit agenta «{name}».",
            "items": [{"file": "instructions.md"}]
        },
        "nodes": [
            {"id":"outline","type":"script","update":{"note":"agent:"+slug},"depends":[]},
            {"id":"fork","type":"fanout","items":"{{ctx.items}}","depends":["outline"]},
            {"id":"final","type":"llm.generate","prompt":"Create an integration plan {ЗЗФ0З}: short and clear.","out":"final_branch","depends":["fork"]},
            {"id":"gather","type":"join","from":"fork","out":"joined","select":{"file":"{{item.file}}","text":"{{ctx.final_branch}}"},"mode":"list","await_nodes":["final"],"depends":["final"]}
        ]
    }
    files.append({
        "path": f"{TEMPL_DIR}/agent_{slug}_auto.yaml",
        "content": json.dumps(plan, ensure_ascii=False, indent=2)
    })
    return files

def _safe_register():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return None
    return register

def _reg():
    register = _safe_register()
    if not register:
        return

    # 1) agent.builder.templates.list
    def a_list(args: Dict[str,Any]):
        return {"ok": True, "templates": _templates_list(), "ab": AB_SLOT}
    register("agent.builder.templates.list", {}, {"ok":"bool"}, 1, a_list)

    # 2) agent.builder.describe
    def a_desc(args: Dict[str,Any]):
        goal = str(args.get("goal","") or "").strip()
        audience = str(args.get("audience","") or "").strip()
        domain = str(args.get("domain","any") or "any")
        name = args.get("name") or ( "EkoRazum" if "sustain" in domain or "eko" in goal.lower() else "Generalist-Agent" )
        spec = {
            "name": name,
            "description": f"Agent for target: ZZF0Z; audience: ZZF1ZZ; domain: ZZF2ZZ.",
            "instructions": "Be helpful, strictly factual, explain briefly, suggest next steps.",
            "capabilities": ["web.browse","files.analyze","plans.cascade","rules.policy.hints"],
            "hints": {
                "cascade_endpoints": { "plan": "/thinking/cascade/plan", "execute": "/thinking/cascade/execute" }
            }
        }
        return {"ok": True, "spec": spec, "ab": AB_SLOT}
    register("agent.builder.describe", {"goal":"str","audience":"str","domain":"str","name":"str"}, {"ok":"bool"}, 2, a_desc)

    # 3) agent.builder.plan.generate
    def a_plan(args: Dict[str,Any]):
        goal = str(args.get("goal","") or "").strip()
        note = str(args.get("note","") or "")
        plan = _plan_skeleton(goal, note)
        return {"ok": True, "plan": plan, "ab": AB_SLOT}
    register("agent.builder.plan.generate", {"goal":"str","note":"str"}, {"ok":"bool"}, 3, a_plan)

    # 4) agent.builder.scaffold.files - generate files (without application)
    def a_files(args: Dict[str,Any]):
        spec = dict(args.get("spec") or {})
        files = _make_files_for(spec)
        return {"ok": True, "files": files, "apply_hint":"use agent.builder.apply with ESTER_AGENT_BUILDER_WRITE=1 and AB=A", "ab": AB_SLOT}
    register("agent.builder.scaffold.files", {"spec":"object"}, {"ok":"bool"}, 5, a_files)

    # 5) agent.builder.apply - apply files via Sodesmyth (A/B+flags)
    def a_apply(args: Dict[str,Any]):
        spec = dict(args.get("spec") or {})
        preview_only = bool(args.get("preview_only", True))
        files = _make_files_for(spec)
        # Always check with a test, even in preview
        test_rep = {}
        try:
            from modules.self.codegen import test_files, guarded_apply  # type: ignore
            test_rep = test_files(files, "")
            ok_test = bool(test_rep.get("ok", True))
            if preview_only or (AB_SLOT!="A") or (not ALLOW_WRITE):
                return {"ok": ok_test, "preview": True, "files": files, "test": test_rep, "why":"preview_or_AB_or_flag", "ab": AB_SLOT}
            # Recording only with A-slot and ALLOW_WRITE enabled
            apply_rep = guarded_apply(files)
            return {"ok": bool(apply_rep.get("ok", False)), "preview": False, "apply": apply_rep, "ab": AB_SLOT}
        except Exception as e:
            return {"ok": False, "error": f"codesmith:{e}", "preview": True, "files": files, "test": test_rep, "ab": AB_SLOT}
    register("agent.builder.apply", {"spec":"object","preview_only":"bool"}, {"ok":"bool"}, 20, a_apply)

_reg()
# c=a+b.