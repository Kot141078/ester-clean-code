# -*- coding: utf-8 -*-
"""modules/meta/bandit.py - mnogorukie bandity (UCB1, Thompson) dlya vybora “ruk” (kandidatov).
Khranenie (ESTER_DATA_ROOT):
  - data/meta/bandit/<name>/arms.json [{id, stats}]
  - data/meta/bandit/<name>/events.jsonl log
  - data/app/meta/policy_{A,B}.json (A/B-sloty dlya meta-politik)
  - data/app/meta/meta_policy_active.json {"active":"A"|"B"}"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os, json, math, random, pathlib, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DATA_ROOT = pathlib.Path(os.getenv("ESTER_DATA_ROOT") or (pathlib.Path.cwd() / "data"))
BANDIT_DIR = DATA_ROOT / "meta" / "bandit"
APP_META_DIR = DATA_ROOT / "app" / "meta"
BANDIT_DIR.mkdir(parents=True, exist_ok=True)
APP_META_DIR.mkdir(parents=True, exist_ok=True)

def _json_atomic(path: pathlib.Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _state_dir(name: str) -> pathlib.Path:
    p = BANDIT_DIR / name
    p.mkdir(parents=True, exist_ok=True)
    return p

def init(name: str, arms: List[Dict[str, Any]]) -> Dict[str, Any]:
    """arms: [{id: 'cfgA', prior_success:0, prior_fail:0, meta: {...}}, ...]"""
    sd = _state_dir(name)
    _json_atomic(sd / "arms.json", arms)
    return {"ok": True, "name": name, "arms": len(arms)}

def list_arms(name: str) -> List[Dict[str, Any]]:
    sd = _state_dir(name)
    try:
        return json.loads((sd / "arms.json").read_text(encoding="utf-8"))
    except Exception:
        return []

def _log(name: str, ev: Dict[str, Any]) -> None:
    p = _state_dir(name) / "events.jsonl"
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")

def pull_ucb1(name: str, step: int) -> Dict[str, Any]:
    arms = list_arms(name)
    if not arms:
        raise RuntimeError("no arms")
    # UCB1 index
    def ucb(a):
        s = float(a.get("success", 0) + a.get("prior_success", 0))
        f = float(a.get("fail", 0) + a.get("prior_fail", 0))
        n = max(1.0, s + f)
        p = s / n
        bonus = math.sqrt(max(0.0, 2.0 * math.log(max(1.0, step))) / n)
        return p + bonus
    idx = max(range(len(arms)), key=lambda i: ucb(arms[i]))
    arm = arms[idx]
    _log(name, {"t": time.time(), "step": step, "algo": "ucb1", "choose": arm.get("id")})
    return arm

def pull_thompson(name: str) -> Dict[str, Any]:
    arms = list_arms(name)
    if not arms:
        raise RuntimeError("no arms")
    def sample(a):
        s = float(a.get("success", 0) + a.get("prior_success", 1.0))
        f = float(a.get("fail", 0) + a.get("prior_fail", 1.0))
        return random.betavariate(max(0.001, s), max(0.001, f))
    idx = max(range(len(arms)), key=lambda i: sample(arms[i]))
    arm = arms[idx]
    _log(name, {"t": time.time(), "algo": "thompson", "choose": arm.get("id")})
    return arm

def update(name: str, arm_id: str, reward: float, threshold: float = 0.5) -> Dict[str, Any]:
    arms = list_arms(name)
    for a in arms:
        if a.get("id") == arm_id:
            if reward >= threshold:
                a["success"] = int(a.get("success", 0)) + 1
            else:
                a["fail"] = int(a.get("fail", 0)) + 1
            _json_atomic(_state_dir(name) / "arms.json", arms)
            _log(name, {"t": time.time(), "update": arm_id, "reward": reward})
            return {"ok": True}
    return {"ok": False, "error": "arm not found"}

# --- AB slots for meta-policy (safe self-editor) ---

def _meta_active_file() -> pathlib.Path:
    return APP_META_DIR / "meta_policy_active.json"

def _meta_slot_path(slot: str) -> pathlib.Path:
    return APP_META_DIR / f"meta_policy_{slot}.json"

def get_active_meta_slot() -> str:
    meta = _meta_active_file()
    if meta.exists():
        try:
            j = json.loads(meta.read_text(encoding="utf-8"))
            if j.get("active") in ("A", "B"):
                return j["active"]
        except Exception:
            pass
    return (os.getenv("ESTER_META_AB") or "A").upper()[:1]

def set_active_meta_slot(slot: str) -> None:
    _json_atomic(_meta_active_file(), {"active": slot})

def stage_meta_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    """We write the policy in the **inactive** slot, there is no return (we will wash it separately and manually)."""
    active = get_active_meta_slot()
    inactive = "B" if active == "A" else "A"
    _json_atomic(_meta_slot_path(inactive), policy)
    return {"ok": True, "staged_to": inactive, "file": str(_meta_slot_path(inactive))}