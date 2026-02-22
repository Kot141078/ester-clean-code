# -*- coding: utf-8 -*-
"""
modules/meta/trials.py — upravlenie ispytaniyami (Trials) dlya meta-optimizatsii.
Khranenie (pod ESTER_DATA_ROOT):
  - data/meta/trials/<trial_id>/spec.json
  - data/meta/trials/<trial_id>/episodes.jsonl
  - data/meta/trials/<trial_id>/status.json
Integratsiya: adapter otsenivaet epizod i vozvraschaet metriki.
Bez zavisimostey ot kaskada; closed-box.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os, json, time, pathlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DATA_ROOT = pathlib.Path(os.getenv("ESTER_DATA_ROOT") or (pathlib.Path.cwd() / "data"))
TRIALS_DIR = DATA_ROOT / "meta" / "trials"
TRIALS_DIR.mkdir(parents=True, exist_ok=True)

def _trial_dir(tid: str) -> pathlib.Path:
    return TRIALS_DIR / tid

def _json_atomic(path: pathlib.Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def create_spec(tid: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Sozdat/perezapisat spetsifikatsiyu ispytaniya (idempotent)."""
    d = _trial_dir(tid)
    d.mkdir(parents=True, exist_ok=True)
    _json_atomic(d / "spec.json", spec)
    if not (d / "status.json").exists():
        _json_atomic(d / "status.json", {"created": time.time(), "episodes": 0})
    return {"ok": True, "id": tid}

def list_specs() -> List[Dict[str, Any]]:
    out = []
    for p in sorted(TRIALS_DIR.glob("*")):
        if not p.is_dir(): 
            continue
        try:
            spec = json.loads((p / "spec.json").read_text(encoding="utf-8"))
        except Exception:
            spec = {}
        out.append({"id": p.name, "spec": spec})
    return out

def get_spec(tid: str) -> Optional[Dict[str, Any]]:
    p = _trial_dir(tid) / "spec.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def append_episode(tid: str, episode: Dict[str, Any]) -> None:
    p = _trial_dir(tid) / "episodes.jsonl"
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(episode, ensure_ascii=False) + "\n")
    stp = _trial_dir(tid) / "status.json"
    try:
        st = json.loads(stp.read_text(encoding="utf-8"))
    except Exception:
        st = {}
    st["episodes"] = int(st.get("episodes", 0)) + 1
    st["updated"] = time.time()
    _json_atomic(stp, st)

# --- zapusk epizoda cherez peredannyy adapter (sm. modules.judge.adapters) ---

def run_episode(tid: str, adapter, task: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Zapuskaet odin epizod: adapter.evaluate(config, task) -> metrics.
    Sokhranyaet zapis i vozvraschaet metriki.
    """
    t0 = time.time()
    res = {"error": "no adapter"}
    try:
        res = adapter.evaluate(config=config, task=task)
        ok = True
    except Exception as e:
        ok = False
        res = {"error": str(e)}
    episode = {
        "t": time.time(),
        "ok": ok,
        "task": task,
        "config": config,
        "metrics": res,
        "dt": time.time() - t0
    }
    append_episode(tid, episode)
    return {"ok": ok, "metrics": res, "dt": episode["dt"]}