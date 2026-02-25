# -*- coding: utf-8 -*-
"""rule_engine — prostoy dvizhok pravil + zagruzka bandla avtomatizatsiy i ustanovka triggerov.

MOSTY:
- Yavnyy: routes/routes_rules.py ↔ (load_rules, install_automation_triggers, run_automation, evaluate).
- Skrytyy #1: (Faylovaya sistema ↔ Politika) - YAML/JSON config ischetsya v ./config/rules.yaml (ili RULES_FILE).
- Skrytyy #2: (Planirovschik ↔ Logika) — install_automation_triggers gotovit plan; esli est modules.scheduler_engine,
              myagko pytaemsya ustanovit triggery cherez ego API (bez zhestkoy zavisimosti).

ZEMNOY ABZATs:
Dumay ob etom module kak o “pulte avtomatiki”: on chitaet pravila, proveryaet usloviya i libo
zapuskaet deystvie, libo soobschaet "propusk". Po umolchaniyu vse integratsii bezopasnye (dry-run)
i ne trebuyut seti/BD - prigodno dlya zakrytoy korobki.
# c=a+b"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import json, os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# ---- public interface of this module ----
__all__ = [
    "evaluate",
    "load_rules",
    "install_automation_triggers",
    "run_automation",
    "match_rule",
    "dedup_block",
    "build_offer",
    "RulesBundle",
]

# ---- primitive checking of conditions (as it was) ----

def _check(cond: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
    var = cond.get("var")
    op = (cond.get("op") or "eq").lower()
    val = cond.get("value")
    cur = ctx.get(var)
    if op == "eq": return cur == val
    if op == "ne": return cur != val
    if op == "gt": return (cur or 0) > val
    if op == "lt": return (cur or 0) < val
    if op == "ge": return (cur or 0) >= val
    if op == "le": return (cur or 0) <= val
    if op == "in": return cur in (val or [])
    if op == "contains": 
        return (val in (cur or [])) or (isinstance(cur, str) and isinstance(val, str) and val in cur)
    return False  # neizvestnyy operator

def evaluate(context: Dict[str, Any] | None, rules: List[Dict[str, Any]] | None) -> Dict[str, Any]:
    """
    Pravila formata:
      [{"if":[{"var":"risk","op":"gt","value":5}], "then":{"action":"flag"}}]
    """
    ctx = dict(context or {})
    res: List[Dict[str, Any]] = []
    for r in (rules or []):
        conds = r.get("if") or []
        if all(_check(c, ctx) for c in conds):
            res.append(r.get("then") or {})
    return {"ok": True, "decisions": res}

# ---- struktura bandla pravil ----

@dataclass
class RulesBundle:
    version: Optional[str]
    defaults: Dict[str, Any]
    sources: Dict[str, Any]
    pipes: Dict[str, Any]
    conditions: Dict[str, Any]
    automations: Dict[str, Dict[str, Any]]
    path: Optional[str] = None  # otkuda zagruzhali

# ---- zagruzka YAML/JSON s pravilami ----

def _project_root() -> Path:
    # 1) env ESTER_ROOT
    env = os.getenv("ESTER_ROOT")
    if env:
        p = Path(env).resolve()
        if p.exists():
            return p
    # 2) ryadom s app.py
    here = Path.cwd().resolve()
    for up in [here] + list(here.parents):
        if (up / "app.py").exists():
            return up
    return here

def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def _try_parse_yaml_or_json(text: str) -> Dict[str, Any]:
    # first YML (if installed), then ZhSON
    try:
        import yaml  # type: ignore
        obj = yaml.safe_load(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {}

def _as_automations_map(obj: Any) -> Dict[str, Dict[str, Any]]:
    if isinstance(obj, dict):
        # normalizuem id vnutri
        out: Dict[str, Dict[str, Any]] = {}
        for k, v in obj.items():
            d = dict(v or {})
            d.setdefault("id", k)
            out[str(k)] = d
        return out
    if isinstance(obj, list):
        out: Dict[str, Dict[str, Any]] = {}
        for item in obj:
            if not isinstance(item, dict): 
                continue
            aid = str(item.get("id") or f"auto_{len(out)+1}")
            d = dict(item)
            d["id"] = aid
            out[aid] = d
        return out
    return {}

def _default_bundle() -> RulesBundle:
    demo = {
        "version": "1.0",
        "defaults": {},
        "sources": {},
        "pipes": {},
        "conditions": {},
        "automations": {
            "sample_ping": {
                "id": "sample_ping",
                "trigger": {"cron": "*/15 * * * *"},  # kazhdye 15 minut (demo)
                "if": [],
                "then": {"type": "log", "message": "sample automation fired"}
            }
        }
    }
    a = _as_automations_map(demo.get("automations", {}))
    return RulesBundle(
        version=str(demo.get("version")),
        defaults=dict(demo.get("defaults", {})),
        sources=dict(demo.get("sources", {})),
        pipes=dict(demo.get("pipes", {})),
        conditions=dict(demo.get("conditions", {})),
        automations=a,
        path=None,
    )

def load_rules(path: Optional[str] = None) -> RulesBundle:
    """Zagruzhaet bundle pravil iz YAML/JSON.
    Ischem v poryadke:
      1) path argument
      2) env RULES_FILE
      3) ./config/rules.yaml
      4)./rules.yaml
    Pri oshibke - otdaem defoltnyy bandl (bez padeniya)."""
    cand: List[Path] = []
    if path:
        cand.append(Path(path))
    env = os.getenv("RULES_FILE")
    if env:
        cand.append(Path(env))
    root = _project_root()
    cand.extend([root / "config" / "rules.yaml", root / "rules.yaml"])

    for p in cand:
        try:
            if p.exists():
                data = _try_parse_yaml_or_json(_read_text(p))
                if data:
                    a = _as_automations_map(data.get("automations", {}))
                    return RulesBundle(
                        version=str(data.get("version")) if data.get("version") is not None else None,
                        defaults=dict(data.get("defaults", {})),
                        sources=dict(data.get("sources", {})),
                        pipes=dict(data.get("pipes", {})),
                        conditions=dict(data.get("conditions", {})),
                        automations=a,
                        path=str(p),
                    )
        except Exception:
            # soft fullback - just try the next option
            continue
    return _default_bundle()

# ---- setting triggers (soft integration with scheduler) ----

def install_automation_triggers(bundle: RulesBundle) -> Dict[str, Any]:
    """Prepares a trigger plan for the scheduler and, if modules.scheduler_engine is available,
    gently trying to stop them. Returns a deterministic report."""
    autos = bundle.automations or {}
    plan: List[Dict[str, Any]] = []
    for aid, a in autos.items():
        trig = a.get("trigger") or {}
        if not trig:
            continue
        # We support several popular forms
        if isinstance(trig, dict):
            if "cron" in trig:
                plan.append({"id": aid, "type": "cron", "expr": str(trig["cron"])})
            if "every_sec" in trig:
                plan.append({"id": aid, "type": "interval", "seconds": int(trig["every_sec"])})
            if "interval_sec" in trig:
                plan.append({"id": aid, "type": "interval", "seconds": int(trig["interval_sec"])})
        elif isinstance(trig, str):
            plan.append({"id": aid, "type": "cron", "expr": trig})

    # Let's try to delegate to a real installation if there is a corresponding API
    delegated = False
    try:
        # possible signatures found in projects
        from modules.scheduler_engine import install_triggers as _install_triggers  # type: ignore
        res = _install_triggers(plan)  # type: ignore
        if isinstance(res, dict):
            return {"ok": True, "installed": res.get("installed", plan), "delegated": True}
        delegated = True
    except Exception:
        pass
    try:
        from modules.scheduler_engine import register_triggers as _register_triggers  # type: ignore
        _register_triggers(plan)  # type: ignore
        delegated = True
    except Exception:
        pass

    return {
        "ok": True,
        "installed": plan,
        "delegated": delegated,
        "bundle_path": bundle.path,
        "count": len(plan),
    }

# ---- manual start of automation ----

def _conditions_passed(conds: Any, context: Dict[str, Any]) -> bool:
    conds = conds or []
    try:
        return all(_check(c, context) for c in conds)
    except Exception:
        return False

def run_automation(bundle: RulesBundle, automation_id: str, *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Performs automation by ID (safe mode - without external I/O).
    Returns ZZF0Z"""
    autos = bundle.automations or {}
    a = autos.get(automation_id)
    if not a:
        return {"ok": False, "error": "unknown_automation", "id": automation_id}

    ctx = dict(context or {})
    if not _conditions_passed(a.get("if"), ctx):
        return {"ok": True, "id": automation_id, "executed": False, "skipped": "conditions_false"}

    action = a.get("then") or a.get("action") or {}
    # A/B-slot: v B — vsegda dry-run
    ab = (os.getenv("ESTER_RULES_AB") or "A").strip().upper()
    dry = (ab == "B")

    # Mini-performer without external effects; for real actions we leave “echo”
    result = {"type": action.get("type") or "noop", "echo": {k: v for k, v in action.items() if k != "type"}}

    return {
        "ok": True,
        "id": automation_id,
        "executed": not dry,
        "dry_run": dry,
        "action": result,
        "context_excerpt": {k: ctx[k] for k in list(ctx)[:5]},  # don't swell the answer
    }


# ---- proactive compatibility helpers ----

def _parse_iso(ts: str):
    from datetime import datetime

    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def _window_seconds(expr: str) -> int:
    s = str(expr or "").strip().lower()
    if not s:
        return 0
    mul = 1
    if s.endswith("h"):
        mul = 3600
        s = s[:-1]
    elif s.endswith("m"):
        mul = 60
        s = s[:-1]
    elif s.endswith("d"):
        mul = 86400
        s = s[:-1]
    try:
        return int(float(s) * mul)
    except Exception:
        return 0


def match_rule(rule: Dict[str, Any], state: Dict[str, Any], now) -> bool:
    cond = str((rule or {}).get("when") or "").strip().lower()
    if not cond:
        return False

    if cond == "new fact":
        medium = state.get("medium") or []
        for item in medium:
            tags = item.get("tags") if isinstance(item, dict) else []
            if "fact" in (tags or []):
                return True
        return False

    if cond.startswith("any(card due < now+1d)"):
        cards = ((state.get("cards") or {}).get("facts") or [])
        for c in cards:
            due = _parse_iso((c or {}).get("due"))
            if due and (due - now).total_seconds() < 86400:
                return True
        return False

    if cond.startswith("last_emotions.anxiety >"):
        try:
            threshold = float(cond.split(">")[1].strip())
        except Exception:
            threshold = 0.0
        cur = float(((state.get("last_emotions") or {}).get("anxiety") or 0.0))
        return cur > threshold

    return False


def dedup_block(rule: Dict[str, Any], state: Dict[str, Any], now) -> bool:
    name = str((rule or {}).get("name") or "")
    win = _window_seconds(str((rule or {}).get("dedup_window") or ""))
    if not name or win <= 0:
        return False
    offers = state.get("offers") or []
    for off in offers:
        if str((off or {}).get("rule") or "") != name:
            continue
        ts = _parse_iso((off or {}).get("timestamp"))
        if ts and (now - ts).total_seconds() <= win:
            return True
    return False


def build_offer(rule: Dict[str, Any], state: Dict[str, Any], now) -> Dict[str, Any]:
    import uuid
    from datetime import timedelta

    ttl_hours = int((rule or {}).get("ttl_hours") or 24)
    return {
        "id": f"offer-{uuid.uuid4().hex[:12]}",
        "rule": str((rule or {}).get("name") or ""),
        "title": str((rule or {}).get("title") or ""),
        "reason": str((rule or {}).get("reason") or ""),
        "priority": str((rule or {}).get("priority") or "normal"),
        "timestamp": now.isoformat(),
        "expires_at": (now + timedelta(hours=ttl_hours)).isoformat(),
        "context": {
            "facts_count": len(((state.get("cards") or {}).get("facts") or [])),
        },
    }
