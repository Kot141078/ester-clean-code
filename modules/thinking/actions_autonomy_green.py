# -*- coding: utf-8 -*-
"""modules/thinking/actions_autonomy_green.py - avtonomnyy vybor tseley i plan deystviy (zelenoe napravlenie).

Mosty:
- Yavnyy: (Mysli/Deystviya ↔ Kaskad/Memory) predlagaem tseli, sobiraem plan s /thinking/act-shagayuschimi vyzovami i otmetkami v profilee.
- Skrytyy #1: (Mysli ↔ Sustainability Kit) podtyagivaem cheklisty/metriki, chtoby tseli byli prizemlennymi i izmerimymi.
- Skrytyy #2: (Mysli ↔ Builder/Report) dobavlyaem shagi describe/plan/scaffold i chernovoy otchet v MD/HTML (cherez uzhe imeyuschiesya deystviya).

Zemnoy abzats:
Ester sama vybiraet zelenye tseli iz svoikh sledov/kontenta i formiruet ispolnimyy plan: opisat agenta, nakidat fayly-prevyu, skomponovat brif/metriki i (po razresheniyu) primenit izmeneniya. Kontrakty API prezhnie.
# c=a+b."""
from __future__ import annotations
import os, io, json, re, time
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_SLOT = (os.getenv("ESTER_AGENT_BUILDER_AB","A") or "A").upper()
ALLOW_WRITE = bool(int(os.getenv("ESTER_AGENT_BUILDER_WRITE","0")))
ALLOW_AUTO  = bool(int(os.getenv("ESTER_AUTONOMY_GREEN","0")))
MAX_GOALS   = int(os.getenv("ESTER_AUTONOMY_MAX_GOALS","1") or "1")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(ROOT, "data")
SM_STORE = os.path.join(DATA_DIR, "structured_mem", "store.json")
ESTER_MEM = os.path.join(DATA_DIR, "ester_memory.json")
KIT_DIR = os.path.join(ROOT, "docs", "sustainability_kit")
CHECK_DIR = os.path.join(KIT_DIR, "checklists")
METRICS_JSON = os.path.join(KIT_DIR, "metrics.json")

KEY_TERMS = [
    ("energ", 2.0), ("kwh", 2.0), ("elektr", 1.8),
    ("otkhod", 1.8), ("waste", 1.8),
    ("logist", 1.6), ("dostavka", 1.4),
    ("upakov", 1.6), ("plastic", 1.5),
    ("voda", 1.2), ("water", 1.2), ("co2", 2.2), ("co₂", 2.2)
]

def _safe_register():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return None
    return register

def _read_json(path: str):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _scan_memory_candidates() -> List[Tuple[str,float,str]]:
    # Reads memory and counts “hints” for key terms
    cands: Dict[str, float] = {}
    def feed(text: str, source: str):
        s = text.lower()
        score = 0.0
        for kw, w in KEY_TERMS:
            if kw in s:
                score += w
        if score > 0:
            cands[source] = cands.get(source, 0.0) + score

    for path in (SM_STORE, ESTER_MEM):
        obj = _read_json(path)
        if obj is None: continue
        def walk(x: Any):
            if isinstance(x, dict):
                note = str(x.get("note") or x.get("text") or "")
                src  = str(x.get("source") or x.get("from") or x.get("origin") or path)
                if note: feed(note, src)
                for v in x.values(): walk(v)
            elif isinstance(x, list):
                for v in x: walk(v)
        walk(obj)

    # Let's add priorities based on the availability of checklists
    for name in ("smb_quick_audit","zero_waste_event"):
        p = os.path.join(CHECK_DIR, f"{name}.md")
        if os.path.isfile(p):
            cands[f"checklist:{name}"] = cands.get(f"checklist:{name}", 0.0) + 1.0

    # Let's create a set of canonical goals
    goals: List[Tuple[str,float,str]] = []
    pairs = [
        ("Snizit potreblenie elektroenergii na 15% za 6 mes", "energy"),
        ("Reduce waste and increase recycling at events", "waste_event"),
        ("Optimizirovat logistiku posledney mili (-10% CO₂e/zakaz)", "logistics"),
        ("Pereyti na ustoychivuyu upakovku v top-3 SKU", "packaging"),
        ("Sokratit vodopotreblenie na 10% v ofise", "water")
    ]
    # Gently weigh the goals using indicators from memory
    for goal, tag in pairs:
        base = 1.0
        for k, w in KEY_TERMS:
            if (tag in k) or (k in tag):
                base += w*0.1
        # let's start a fight if there are relevant “sources” in memory
        mem_bonus = 0.0
        for src, s in cands.items():
            if tag in src or ("checklist" in src and tag in ("waste_event","energy","packaging")):
                mem_bonus += min(1.0, s*0.05)
        goals.append((goal, base + mem_bonus, f"mem:{len(cands)}; tag:{tag}"))
    # Otsortiruem po score
    goals.sort(key=lambda x: x[1], reverse=True)
    return goals

def _top_goals(n: int) -> List[Dict[str,Any]]:
    c = _scan_memory_candidates()
    n = max(1, n)
    top = c[:n]
    out = []
    for i,(g,score,why) in enumerate(top,1):
        out.append({"rank": i, "goal": g, "score": round(score,2), "why": why})
    return out

def _plan_for_goals(goals: List[Dict[str,Any]]) -> Dict[str,Any]:
    # Putting together a safe step-by-step plan (executed via /thinking/cascade/esesote)
    steps: List[Dict[str,Any]] = []
    # Obschaya otmetka
    steps.append({
        "kind":"mem.passport.append",
        "endpoint":"/thinking/act",
        "body":{"name":"mem.passport.append","args":{"note":"AUTONOMY: start zelenogo plana","meta":{"from":"actions_autonomy_green","n":len(goals)},"source":"thinking://autonomy.green"}}
    })
    # For each goal, add a block of agreed steps
    for g in goals:
        goal = g["goal"]
        # 1) Refleksiya
        steps.append({"kind":"reflect.enqueue","endpoint":"/thinking/reflection/enqueue","body":{"item":{"text":goal,"meta":{"importance":0.6}}}})
        # 2) Opisanie agenta
        steps.append({"kind":"act","endpoint":"/thinking/act","body":{"name":"agent.builder.describe","args":{"goal":goal,"audience":"SMB","domain":"sustainability"}}})
        # 3) Plan agenta
        steps.append({"kind":"act","endpoint":"/thinking/act","body":{"name":"agent.builder.plan.generate","args":{"goal":goal}}})
        # 4) Brif po kitu
        steps.append({"kind":"act","endpoint":"/thinking/act","body":{"name":"sustainability.kit.compose_brief","args":{"goal":goal,"sector":"SMB"}}})
        # 5) Fayly-prevyu
        steps.append({"kind":"act","endpoint":"/thinking/act","body":{"name":"agent.builder.scaffold.files","args":{"spec":{"name":"EkoRazum","description":f"Autonomous target: ZZF0Z","instructions":"Korotko, po delu, izmerimo.","capabilities":["plans.cascade","files.analyze","rules.policy.hints"]}}}})
        # 6) Chernovoy otchet (MD → HTML)
        steps.append({"kind":"act","endpoint":"/thinking/act","body":{"name":"report.compose.md","args":{"title":f"Eco-report: ZZF0Z","goal":goal,"brief":{"outline":[goal]},"checklist_md":"(sm. KIT)","metrics":{}}}})
        steps.append({"kind":"act","endpoint":"/thinking/act","body":{"name":"report.compose.html","args":{"title":f"Eco-report: ZZF0Z","markdown":"(see MD step above)"}}})
        # 7) Application (only if allowed by the environment; otherwise preview)
        steps.append({"kind":"act","endpoint":"/thinking/act","body":{"name":"agent.builder.apply","args":{"spec":{"name":"EkoRazum","description":f"Autonomous target: ZZF0Z"}, "preview_only": not (AB_SLOT=='A' and ALLOW_WRITE)}}})
    return {"ok": True, "goal": "Avtonomnye zelenye tseli", "steps": steps, "ab": AB_SLOT, "auto": ALLOW_AUTO}

def _reg():
    register = _safe_register()
    if not register:
        return

    # 1) autonomy.green.suggest_voice - suggest goals (Esther decides the priority herself)
    def a_suggest(args: Dict[str,Any]):
        hint = str(args.get("hint","") or "")
        n = int(args.get("max_goals") or MAX_GOALS or 1)
        goals = _top_goals(n)
        if not goals:
            goals = [{"rank":1,"goal":"Snizit potreblenie elektroenergii na 15% za 6 mes","score":1.0,"why":"fallback"}]
        return {"ok": True, "ab": AB_SLOT, "auto": ALLOW_AUTO, "goals": goals, "hint": hint}
    register("autonomy.green.suggest_goals", {"hint":"str","max_goals":"int"}, {"ok":"bool"}, 1, a_suggest)

    # 2) autonomy.green.plan - create an executable plan for top goals
    def a_plan(args: Dict[str,Any]):
        n = int(args.get("max_goals") or MAX_GOALS or 1)
        goals = _top_goals(n)
        plan = _plan_for_goals(goals)
        return {"ok": True, "ab": AB_SLOT, "plan": plan, "auto": ALLOW_AUTO}
    register("autonomy.green.plan", {"max_goals":"int"}, {"ok":"bool"}, 2, a_plan)

    # 3) autonomy.green.batch.plan - an explicit packet of targets (if transmitted externally)
    def a_batch(args: Dict[str,Any]):
        goals_in = args.get("goals") or []
        goals = []
        for i,g in enumerate(goals_in,1):
            if isinstance(g, str):
                goals.append({"rank": i, "goal": g, "score": 1.0, "why": "external"})
            elif isinstance(g, dict) and g.get("goal"):
                goals.append({"rank": i, "goal": str(g["goal"]), "score": float(g.get("score",1.0)), "why": "external"})
        if not goals:
            return {"ok": False, "error":"no goals"}
        return {"ok": True, "ab": AB_SLOT, "plan": _plan_for_goals(goals), "auto": ALLOW_AUTO}
    register("autonomy.green.batch.plan", {"goals":"list"}, {"ok":"bool"}, 3, a_batch)

_reg()
# c=a+b.