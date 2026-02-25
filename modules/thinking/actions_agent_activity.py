# -*- coding: utf-8 -*-
"""modules/thinking/actions_agent_activity.py - agregator logov Builder/KIT/Report.

Mosty:
- Yavnyy: (Mysli/Deystviya ↔ Memory/Pravila) sobiraem sobytiya iz pamyati (fayly dannykh) i RuleHub-lenty dlya otobrazheniya v UI.
- Skrytyy #1: (Memory ↔ Analitika) daem filtry/limity i svodnuyu statistiku bez izmeneniya kontraktov API.
- Skrytyy #2: (Kaskad ↔ UX) vozvraschaem strukturu, sovmestimuyu s kaskadom i suschestvuyuschimi admin-instrumentami.

Zemnoy abzats:
Eto "lupa" po sledam Ester: v odin vyzov mozhno uvidet, chto delal Builder/KIT/Report - plany, zametki, result. Pomogaet kontrolyu i razboru poletov, nichego ne lomaet.
# c=a+b."""
from __future__ import annotations
import os, io, json, time, re
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_SLOT = (os.getenv("ESTER_AGENT_BUILDER_AB","A") or "A").upper()

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(ROOT, "data")
SM_STORE = os.path.join(DATA_DIR, "structured_mem", "store.json")
ESTER_MEM = os.path.join(DATA_DIR, "ester_memory.json")

# heuristics for finding our events
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

def _ts_now() -> int:
    return int(time.time())

def _iter_candidates() -> List[Tuple[str, Any]]:
    items: List[Tuple[str, Any]] = []
    for p in (SM_STORE, ESTER_MEM):
        obj = _read_json(p)
        if obj is not None:
            items.append((p, obj))
    return items

def _extract_events(obj: Any, q: str | None = None) -> List[Dict[str, Any]]:
    """Lax parser: we go through dictionaries/lists, pull out notes/fragments,
    Labels sources/times whenever possible. At the same time, we filter by patterns."""
    q = (q or "").strip()
    rx = [re.compile(p, re.I) for p in PATTERNS]
    evs: List[Dict[str, Any]] = []

    def walk(x: Any, path: str = ""):
        try:
            if isinstance(x, dict):
                # recognizes typical fields
                note = str(x.get("note") or x.get("text") or "")
                src  = str(x.get("source") or x.get("from") or x.get("origin") or "")
                ts   = x.get("ts") or x.get("time") or x.get("timestamp")
                # heuristics: what we once put in our profile
                if any(r.search(note) for r in rx) or any(r.search(src) for r in rx):
                    full = json.dumps(x, ensure_ascii=False)
                    if not q or (q.lower() in full.lower()):
                        evs.append({
                            "ts": int(ts or 0),
                            "source": src or "mem",
                            "note": note[:800],
                            "path": path
                        })
                # oboyti detey
                for k,v in x.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(x, list):
                for i,v in enumerate(x):
                    walk(v, f"{path}[{i}]")
        except Exception:
            return
    walk(obj)
    return evs

def _merge_and_sort(all_evs: List[List[Dict[str,Any]]], limit: int) -> List[Dict[str,Any]]:
    merged: List[Dict[str,Any]] = []
    for chunk in all_evs:
        merged.extend(chunk)
    # if there are no timestamps, use the descending index as a surrogate
    def key(e): return int(e.get("ts") or 0)
    merged.sort(key=key, reverse=True)
    if limit > 0:
        merged = merged[:limit]
    # normalizuem ts
    for i,e in enumerate(merged):
        if not e.get("ts"):
            e["ts"] = _ts_now() - i
    return merged

def _stats(evs: List[Dict[str,Any]]) -> Dict[str,int]:
    kinds = {"builder":0,"kit":0,"report":0,"other":0}
    for e in evs:
        note = (e.get("note") or "") + " " + (e.get("source") or "")
        s = note.lower()
        if ("agentbuilder" in s) or ("thinking://agent.builder" in s) or ("actions_build_agent_helper" in s):
            kinds["builder"] += 1
        elif ("kit:" in s) or ("admin_agent_kit" in s) or ("sustainability.kit" in s):
            kinds["kit"] += 1
        elif ("report:" in s) or ("actions_report_export" in s) or ("report.compose" in s):
            kinds["report"] += 1
        else:
            kinds["other"] += 1
    return kinds

def _reg():
    register = _safe_register()
    if not register:
        return

    # 1) agent.activity.scan - collect the latest events with filters
    def a_scan(args: Dict[str,Any]):
        q = str(args.get("q","") or "")
        limit = int(args.get("limit", 50))
        all_evs: List[List[Dict[str,Any]]] = []
        for p,obj in _iter_candidates():
            all_evs.append(_extract_events(obj, q=q))
        merged = _merge_and_sort(all_evs, limit)
        return {"ok": True, "ab": AB_SLOT, "events": merged, "limit": limit}
    register("agent.activity.scan", {"q":"str","limit":"int"}, {"ok":"bool"}, 1, a_scan)

    # 2) agent.activity.stats - summary statistics for the last scan
    # (for simplicity, we will rescan with the same parameters)
    def a_stats(args: Dict[str,Any]):
        q = str(args.get("q","") or "")
        limit = int(args.get("limit", 200))
        all_evs: List[List[Dict[str,Any]]] = []
        for p,obj in _iter_candidates():
            all_evs.append(_extract_events(obj, q=q))
        merged = _merge_and_sort(all_evs, limit)
        return {"ok": True, "ab": AB_SLOT, "stats": _stats(merged), "count": len(merged)}
    register("agent.activity.stats", {"q":"str","limit":"int"}, {"ok":"bool"}, 2, a_stats)

    # 3) agent.activity.digest.plan - mini-plan LLM-daydzhesta (pod /thinking/cascade/execute)
    def a_digest_plan(args: Dict[str,Any]):
        title = str(args.get("title") or "Esther's activity digest")
        q = str(args.get("q","") or "")
        limit = int(args.get("limit", 40))
        plan = {
            "ok": True,
            "goal": f"Collect activity digest: ZZF0Z",
            "steps": [
                {"kind":"reflect.enqueue", "endpoint":"/thinking/reflection/enqueue", "body":{"item":{"text":title, "meta":{"importance":0.5}}}},
                {"kind":"mem.passport.append", "endpoint":"/thinking/act", "body":{"name":"mem.passport.append","args":{"note":"DIGEST: start formirovaniya","meta":{"from":"actions_agent_activity","q":q,"limit":limit},"source":"thinking://digest"}}}
            ],
            "ab": AB_SLOT
        }
        return {"ok": True, "ab": AB_SLOT, "plan": plan}
    register("agent.activity.digest.plan", {"title":"str","q":"str","limit":"int"}, {"ok":"bool"}, 3, a_digest_plan)

_reg()
# c=a+b.