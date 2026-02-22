# -*- coding: utf-8 -*-
"""
RewardHub — edinyy skoring/agregator metrik.
- compute_score: perevodit metriki v skalyarnyy skor
- RewardHub.update(): dobavlyaet sobytie, vedet EMA/schetchik/poslednie znacheniya
- khranenie: $ESTER_DATA_ROOT/meta/reward_hub.json (+ logs/reward_hub.jsonl)
AB:
  A — ispolzuet judge.fold_scores i DEFAULT_WEIGHTS
  B — konservativnaya formula (klipping, shtrafy)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
import os, json, time, math
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# try to import fitness fold from judge
try:
    from ester.modules.judge.fitness import fold_scores as _fold_scores, DEFAULT_WEIGHTS as _J_WEIGHTS  # type: ignore
except Exception:
    try:
        from modules.judge.fitness import fold_scores as _fold_scores, DEFAULT_WEIGHTS as _J_WEIGHTS  # type: ignore
    except Exception:
        _fold_scores = None
        _J_WEIGHTS = {"utility": 2.0, "accuracy": 1.0, "time_sec": -0.1, "err_rate": -1.0}

DATA_ROOT = Path(os.getenv("ESTER_DATA_ROOT") or (Path.cwd() / "data"))
META_DIR = DATA_ROOT / "meta"
META_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = DATA_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = META_DIR / "reward_hub.json"
LOG_FILE = LOG_DIR / "reward_hub.jsonl"

def _json_dump_atomic(obj: Any, path: Path):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _jsonl_append(path: Path, obj: Dict[str, Any]):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def _ab_mode() -> str:
    return (os.getenv("ESTER_REWARD_AB") or "A").upper()[:1]

def _ema_alpha() -> float:
    try:
        return max(0.0, min(1.0, float(os.getenv("ESTER_REWARD_EMA", "0.2"))))
    except Exception:
        return 0.2

def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default

def _fold_like(metrics_list: List[Dict[str, Any]], weights: Dict[str, float]) -> Dict[str, float]:
    # Prostaya zamena, esli net judge.fold_scores
    agg = {"utility":0.0,"accuracy":0.0,"time_sec":0.0,"err_rate":0.0,"tokens_prompt":0.0,"tokens_gen":0.0}
    n = max(1, len(metrics_list))
    for m in metrics_list:
        for k in list(agg.keys()):
            if k in m:
                agg[k] += _safe_float(m[k], 0.0)
    for k in list(agg.keys()):
        agg[k] /= n
    score = 0.0
    for name, w in weights.items():
        score += w * _safe_float(agg.get(name, 0.0), 0.0)
    agg["score"] = score
    return agg

def compute_score(payload: Dict[str, Any], mode: Optional[str]=None, weights: Optional[Dict[str,float]]=None) -> Dict[str, Any]:
    """
    payload: { "metrics": {...} } ILI { "per_task":[{...}, ...] }
    return: { "metrics": {... with score ...} }
    """
    mode = (mode or _ab_mode()).upper()[:1]
    weights = weights or dict(_J_WEIGHTS)
    per_task: List[Dict[str, Any]]
    if "per_task" in payload and isinstance(payload["per_task"], list):
        per_task = payload["per_task"]
    elif "metrics" in payload and isinstance(payload["metrics"], dict):
        per_task = [payload["metrics"]]
    else:
        per_task = []

    if mode == "A":
        if _fold_scores is not None:
            folded = _fold_scores(per_task, weights)  # type: ignore
            return {"metrics": folded}
        else:
            return {"metrics": _fold_like(per_task, weights)}
    else:
        # B — konservativnaya formula
        agg = _fold_like(per_task, weights)
        # Klipping i shtrafy
        acc = max(0.0, min(1.0, agg.get("accuracy", 0.0)))
        util = max(0.0, min(1.0, agg.get("utility", 0.0)))
        t = max(0.05, agg.get("time_sec", 1.0))
        err = max(0.0, min(1.0, agg.get("err_rate", 1.0)))
        # logarifmicheskiy shtraf za vremya i kvadratichnyy za oshibku
        score = 2.0*util + 1.0*acc - 0.15*math.log1p(t) - 1.5*(err**2)
        agg["score"] = score
        return {"metrics": agg}

@dataclass
class RewardHub:
    weights: Dict[str, float] = field(default_factory=lambda: dict(_J_WEIGHTS))
    ema_alpha: float = field(default_factory=_ema_alpha)

    def _load(self) -> Dict[str, Any]:
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"count": 0, "ema": None, "last": None, "mode": _ab_mode()}

    def _save(self, st: Dict[str, Any]) -> None:
        _json_dump_atomic(st, STATE_FILE)

    def update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        comp = compute_score(payload, mode=_ab_mode(), weights=self.weights)
        score = float(comp["metrics"]["score"])
        st = self._load()
        c = int(st.get("count") or 0) + 1
        ema_prev = st.get("ema")
        a = float(self.ema_alpha)
        ema = score if ema_prev is None else (a*score + (1-a)*float(ema_prev))
        st.update({"count": c, "ema": ema, "last": score, "mode": _ab_mode()})
        self._save(st)
        _jsonl_append(LOG_FILE, {"t": time.time(), "mode": _ab_mode(), "score": score, "metrics": comp["metrics"]})
        return {"ok": True, "score": score, "ema": ema, "count": c, "mode": _ab_mode(), "weights": self.weights}

    def summary(self) -> Dict[str, Any]:
        st = self._load()
        return {"ok": True, "state": st, "weights": self.weights, "mode": _ab_mode(), "log": str(LOG_FILE)}

    def reset(self) -> Dict[str, Any]:
        st = {"count": 0, "ema": None, "last": None, "mode": _ab_mode()}
        self._save(st)
        return {"ok": True, "state": st}