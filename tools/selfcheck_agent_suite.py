# -*- coding: utf-8 -*-
"""
tools/selfcheck_agent_suite.py — itogovaya samoproverka Agent Suite (Builder/KIT/Report/Activity/One-Click).

Mosty:
- Yavnyy: (Instrumenty ↔ Mysli/Deystviya) — proveryaem, chto eksheny zaregistrirovany v reestre i dostupny pri importe.
- Skrytyy #1: (Instrumenty ↔ Dokumentatsiya/Statika) — proveryaem nalichie HTML/JS/planov bez izmeneniya servernykh kontraktov.
- Skrytyy #2: (Instrumenty ↔ Bezopasnost) — validiruem A/B-slot i WRITE-flag, rekomenduem RuleHub-preset.

Zemnoy abzats:
Eto «odna knopka proverki»: importiruy sistemu, ubedis, chto Ester vidit vse eksheny, stranitsy i plany. Ni odin kontrakt ne menyaetsya — eto kontrol kachestva.
# c=a+b.
"""
from __future__ import annotations
import os, sys, json, importlib, glob
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

EXPECTED_ACTIONS = [
    # Agent Builder yadro
    "agent.builder.templates.list",
    "agent.builder.describe",
    "agent.builder.plan.generate",
    "agent.builder.scaffold.files",
    "agent.builder.apply",
    # Sustainability Kit
    "sustainability.kit.list",
    "sustainability.kit.get_checklist",
    "sustainability.kit.metrics.list",
    "sustainability.kit.compose_brief",
    # Report
    "report.compose.md",
    "report.compose.html",
    "report.save.files",
    "report.plan.quick",
    # Activity
    "agent.activity.scan",
    "agent.activity.stats",
    "agent.activity.digest.plan",
    # Activity → Report
    "activity.report.compose.md",
    "activity.report.compose.html",
    "activity.report.save",
    "activity.report.plan.quick",
    # One-Click Green
    "oneclick.green.bundle",
    "oneclick.green.apply",
]

HTML_PAGES = [
    "docs/agent_builder.html",
    "docs/agent_builder_kit.html",
    "docs/agent_report.html",
    "docs/agent_activity.html",
    "docs/activity_to_report.html",
    "docs/oneclick_green.html",
    "docs/agent_suite_index.html",
]

STATIC_JS = [
    "static/admin_agent_builder.js",
    "static/admin_agent_kit.js",
    "static/admin_report_export.js",
    "static/admin_agent_activity.js",
    "static/admin_activity_to_report.js",
    "static/admin_oneclick_green.js",
]

PLANS = glob.glob(os.path.join(ROOT, "examples", "plans", "*sustainability*.yaml")) + [
    "examples/plans/agent_builder_plan.yaml",
    "examples/plans/agent_quick_plan_min.yaml",
    "examples/plans/report_min.yaml",
    "examples/plans/activity_digest.yaml",
    "examples/plans/activity_to_report.yaml",
    "examples/plans/oneclick_green_min.yaml",
]

def _exists(path):
    return os.path.isfile(os.path.join(ROOT, path))

def _import_actions():
    # Podkhvatyvaem nashi action-moduli (drop-in): cherez auto-discovery oni gruzyatsya,
    # no zdes prinuditelno importiruem dlya prozrachnosti.
    modules = [
        "modules.thinking.actions_build_agent_helper",
        "modules.thinking.actions_sustainability_kit",
        "modules.thinking.actions_report_export",
        "modules.thinking.actions_agent_activity",
        "modules.thinking.actions_activity_to_report",
        "modules.thinking.actions_oneclick_green",
    ]
    ok = True; errs = []
    for m in modules:
        try:
            importlib.import_module(m)
        except Exception as e:
            ok = False; errs.append(f"{m}: {e}")
    return ok, errs

def _check_registry():
    try:
        from modules.thinking.action_registry import registry  # type: ignore
        names = sorted(list(registry.keys()))
        missing = [a for a in EXPECTED_ACTIONS if a not in names]
        return True, {"registered": names, "missing": missing}
    except Exception as e:
        return False, {"error": str(e)}

def main():
    imp_ok, imp_errs = _import_actions()

    pages = {p: _exists(p) for p in HTML_PAGES}
    js    = {p: _exists(p) for p in STATIC_JS}
    plans = {os.path.relpath(p, ROOT): os.path.isfile(p) for p in PLANS}

    reg_ok, reg_payload = _check_registry()

    env = {
        "AB": os.getenv("ESTER_AGENT_BUILDER_AB", "A"),
        "WRITE": os.getenv("ESTER_AGENT_BUILDER_WRITE", "0"),
    }

    ok = imp_ok and reg_ok and all(pages.values()) and all(js.values()) and all(plans.values())
    rep = {
        "ok": ok,
        "env": env,
        "import_ok": imp_ok,
        "import_errors": imp_errs,
        "pages": pages,
        "static_js": js,
        "plans": plans,
        "registry": reg_payload,
        "hint": "RuleHub preset: docs/agent_builder_rulehub_preset.yaml; zapis tolko pri AB='A' i WRITE='1'."
    }

    if "--json" in sys.argv:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("OK" if ok else "FAIL")
        print(json.dumps(rep, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
# c=a+b.