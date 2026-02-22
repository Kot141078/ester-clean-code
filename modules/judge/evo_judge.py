# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Optional
import os, json, time, pathlib, random

from .search_spaces import DEFAULT_SPACE, initial_population_size, generations, mutation_rate, crossover_rate, tournament_k
from .adapters import BaseAdapter
from .fitness import fold_scores, DEFAULT_WEIGHTS
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DATA_ROOT = pathlib.Path(os.getenv("ESTER_DATA_ROOT") or (pathlib.Path.cwd() / "data"))
LOG_DIR = DATA_ROOT / "logs" / "evojudge"
APP_DIR = DATA_ROOT / "app"
PROFILES_DIR = APP_DIR / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

def _json_dump_atomic(obj: Any, path: pathlib.Path):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _jsonl_append(path: pathlib.Path, obj: Dict[str, Any]):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def _active_slot_file() -> pathlib.Path:
    return APP_DIR / "judge_profile_active.json"

def _slot_path(slot: str) -> pathlib.Path:
    return PROFILES_DIR / f"judge_profile_{slot}.json"

def _get_active_slot() -> str:
    meta = _active_slot_file()
    if meta.exists():
        try:
            j = json.loads(meta.read_text(encoding="utf-8"))
            if j.get("active") in ("A", "B"):
                return j["active"]
        except Exception:
            pass
    return os.getenv("AB_MODE", "A").upper()[:1] if os.getenv("AB_MODE") else "A"

def _set_active_slot(slot: str) -> None:
    _json_dump_atomic({"active": slot}, _active_slot_file())

def _inactive_slot(active: str) -> str:
    return "B" if active == "A" else "A"

def _sample_from_space(space: Dict[str, Any]) -> Dict[str, Any]:
    def pick(v):
        if isinstance(v, list) and v and not isinstance(v[0], dict):
            return random.choice(v)
        if isinstance(v, dict):
            return {k: pick(vv) for k, vv in v.items()}
        return v
    return {k: pick(v) for k, v in space.items()}

def _crossover(a: Dict[str, Any], b: Dict[str, Any], rate: float) -> Dict[str, Any]:
    """Safe crossover over the UNION of keys; no uninitialized reads."""
    out: Dict[str, Any] = {}
    keys = set(a.keys()) | set(b.keys())
    for k in keys:
        va = a.get(k, None)
        vb = b.get(k, va)
        if isinstance(va, dict) and isinstance(vb, dict):
            out[k] = _crossover(va, vb, rate)
        elif va is None:
            out[k] = vb
        elif vb is None:
            out[k] = va
        else:
            out[k] = random.choice([va, vb]) if random.random() < rate else va
    return out

def _mutate(cfg: Dict[str, Any], space: Dict[str, Any], rate: float) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in cfg.items():
        sp = space.get(k)
        if isinstance(v, dict) and isinstance(sp, dict):
            out[k] = _mutate(v, sp, rate)
        else:
            if isinstance(sp, list) and sp and random.random() < rate:
                out[k] = random.choice(sp)
            else:
                out[k] = v
    # also consider keys present in space but not in cfg
    for k, sp in space.items():
        if k not in out:
            if isinstance(sp, list) and sp:
                out[k] = random.choice(sp)
            elif isinstance(sp, dict):
                out[k] = _mutate({}, sp, rate)
    return out

def _tournament_select(pop: List[Tuple[Dict[str, Any], float]], k: int) -> Dict[str, Any]:
    group = random.sample(pop, k=min(k, len(pop)))
    group.sort(key=lambda x: x[1], reverse=True)
    return group[0][0]

@dataclass
class EvoJudgeRunner:
    adapter: BaseAdapter
    tasks: List[Dict[str, Any]]
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    space: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_SPACE))
    pop_size: int = initial_population_size()
    max_generations: int = generations()
    crossover: float = crossover_rate()
    mutation: float = mutation_rate()
    budget_max_time_sec: float = 1800.0
    seed: Optional[int] = None
    patience: int = 2
    label: str = "default"

    def __post_init__(self):
        if self.seed is not None:
            random.seed(self.seed)

    def _save_profile_to_slot(self, slot: str, cfg: Dict[str, Any]):
        path = _slot_path(slot)
        _json_dump_atomic(cfg, path)
        return path

    def _evaluate_config(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        per_task = []
        for t in self.tasks:
            try:
                res = self.adapter.evaluate(cfg, t)
            except Exception as e:
                res = {"utility": 0.0, "accuracy": 0.0, "time_sec": 1.0, "err_rate": 1.0, "error": str(e)}
            per_task.append(res)
        agg = fold_scores(per_task, self.weights)
        return {"metrics": agg, "per_task": per_task}

    def run(self) -> Dict[str, Any]:
        t0 = time.time()
        active = _get_active_slot()
        inactive = _inactive_slot(active)

        population: List[Dict[str, Any]] = []
        active_path = _slot_path(active)
        if active_path.exists():
            try:
                population.append(json.loads(active_path.read_text(encoding="utf-8")))
            except Exception:
                pass
        while len(population) < self.pop_size:
            population.append(_sample_from_space(self.space))

        best_score = -1e9
        best_cfg: Optional[Dict[str, Any]] = None
        stagnation = 0
        log_path = LOG_DIR / f"evojudge_{self.label}.jsonl"

        for gen in range(self.max_generations):
            scored: List[Tuple[Dict[str, Any], float, Dict[str, Any]]] = []
            for i, cfg in enumerate(population):
                ev = self._evaluate_config(cfg)
                score = float(ev["metrics"]["score"])
                scored.append((cfg, score, ev))
                _jsonl_append(log_path, {"t": time.time(), "gen": gen, "i": i, "score": score, "cfg": cfg, "ev": ev})

            scored.sort(key=lambda x: x[1], reverse=True)
            top_cfg, top_score, top_ev = scored[0]
            improved = top_score > best_score + 1e-6
            if improved:
                best_score = top_score
                best_cfg = top_cfg
                stagnation = 0
                self._save_profile_to_slot(inactive, best_cfg)
                _set_active_slot(inactive)
                active, inactive = inactive, _inactive_slot(inactive)
            else:
                stagnation += 1

            if time.time() - t0 > self.budget_max_time_sec:
                break
            if stagnation >= self.patience:
                break

            new_pop: List[Dict[str, Any]] = []
            elites = max(1, self.pop_size // 4)
            for j in range(elites):
                new_pop.append(scored[j][0])
            pool = [(cfg, sc) for cfg, sc, _ in scored]
            while len(new_pop) < self.pop_size:
                p1 = _tournament_select(pool, tournament_k())
                p2 = _tournament_select(pool, tournament_k())
                child = _crossover(p1, p2, self.crossover)
                child = _mutate(child, self.space, self.mutation)
                new_pop.append(child)
            population = new_pop

        return {
            "ok": True,
            "best_score": best_score,
            "active_slot": _get_active_slot(),
            "log": str(log_path),
            "profile_A": str(_slot_path("A")),
            "profile_B": str(_slot_path("B")),
        }