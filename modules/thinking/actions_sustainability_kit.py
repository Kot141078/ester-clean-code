# -*- coding: utf-8 -*-
"""
modules/thinking/actions_sustainability_kit.py — deystviya kita ustoychivogo razvitiya.

Mosty:
- Yavnyy: (Mysli/Deystviya ↔ Dokumentatsiya/Dannye) chitaem cheklisty iz docs/ i faktory iz JSON, otdaem cherez /thinking/act.
- Skrytyy #1: (Kaskad ↔ UX) vozvraschaem struktury, srazu prigodnye dlya /thinking/cascade/execute (admin_cascade.js).
- Skrytyy #2: (Pravila ↔ Memory) rezultaty mozhno logirovat v profile/zhurnal temi zhe mekhanizmami, bez novykh kontraktov.

Zemnoy abzats:
Eto «yaschik s instrumentami» dlya zelenykh agentov: cheklisty, faktory i kompaktnye brify. Ester poluchaet gotovye kuski znaniy dlya planov i otchetov — nichego ne menyaya v API.
# c=a+b.
"""
from __future__ import annotations
import os, json, io, glob
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_SLOT = (os.getenv("ESTER_AGENT_BUILDER_AB","A") or "A").upper()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS_DIR = os.path.join(BASE_DIR, "docs", "sustainability_kit")
CHECKLISTS_DIR = os.path.join(DOCS_DIR, "checklists")
METRICS_FILE = os.path.join(DOCS_DIR, "metrics.json")

def _read_text(path: str) -> str:
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()

def _read_json(path: str):
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _safe_register():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return None
    return register

def _list_checklists():
    os.makedirs(CHECKLISTS_DIR, exist_ok=True)
    items = []
    for p in sorted(glob.glob(os.path.join(CHECKLISTS_DIR, "*.md"))):
        slug = os.path.splitext(os.path.basename(p))[0]
        items.append({"id": slug, "path": p})
    return items

def _metrics():
    os.makedirs(DOCS_DIR, exist_ok=True)
    if not os.path.isfile(METRICS_FILE):
        return {"ok": False, "error": "metrics.json not found", "ab": AB_SLOT}
    data = _read_json(METRICS_FILE)
    return {"ok": True, "data": data, "ab": AB_SLOT}

def _compose_brief(goal: str, sector: str):
    # Mini-logika komponovki (bez LLM): svyazyvaem tsel/sektor s tipovymi shagami
    outline = [
        f"Tsel: {goal or '—'}",
        f"Sektor/kontekst: {sector or '—'}",
        "Metriki: CO₂e (t/god, t/ed.), kWh, otkhody (kg), voda (m³).",
        "Shagi: audit → bystraya ekonomiya → strukturnye mery → monitoring.",
        "Instrumenty: plany kaskada, cheklisty, RuleHub-politiki, otchetnost."
    ]
    # Podskazki po istochnikam dannykh
    hints = {
        "checklists": [x["id"] for x in _list_checklists()],
        "metrics_source": "docs/sustainability_kit/metrics.json",
        "plans_suggested": [
            "examples/plans/agent_sustainability_quickstart.yaml",
            "examples/plans/agent_sustainability_deep.yaml"
        ]
    }
    return {"ok": True, "ab": AB_SLOT, "brief": {"outline": outline, "hints": hints}}

def _reg():
    register = _safe_register()
    if not register:
        return

    # 1) Spisok materialov kita
    def a_list(args):
        items = _list_checklists()
        exists_metrics = os.path.isfile(METRICS_FILE)
        return {"ok": True, "ab": AB_SLOT, "checklists": items, "has_metrics": bool(exists_metrics)}
    register("sustainability.kit.list", {}, {"ok":"bool"}, 1, a_list)

    # 2) Vydat cheklist po id
    def a_get(args):
        cid = str(args.get("id","") or "").strip()
        if not cid:
            return {"ok": False, "error": "id required", "ab": AB_SLOT}
        path = os.path.join(CHECKLISTS_DIR, f"{cid}.md")
        if not os.path.isfile(path):
            return {"ok": False, "error": "not found", "ab": AB_SLOT}
        return {"ok": True, "ab": AB_SLOT, "id": cid, "markdown": _read_text(path)}
    register("sustainability.kit.get_checklist", {"id":"str"}, {"ok":"bool"}, 2, a_get)

    # 3) Faktory/metriki CO2e
    def a_metrics(args):
        return _metrics()
    register("sustainability.kit.metrics.list", {}, {"ok":"bool"}, 3, a_metrics)

    # 4) Komponovka kratkogo brifa pod tsel/sektor
    def a_brief(args):
        goal = str(args.get("goal","") or "")
        sector = str(args.get("sector","") or "")
        return _compose_brief(goal, sector)
    register("sustainability.kit.compose_brief", {"goal":"str","sector":"str"}, {"ok":"bool"}, 4, a_brief)

_reg()
# c=a+b.