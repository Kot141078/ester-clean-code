# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import sys
# Ensure project root on sys.path for both "ester.*" and "modules.*" layouts
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse, json, shlex
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Flexible imports
try:
    from ester.modules.judge.adapters import DummyAdapter, ExternalProcessAdapter, HTTPAdapter  # type: ignore
    from ester.modules.judge.fitness import fold_scores, DEFAULT_WEIGHTS  # type: ignore
except Exception:
    from modules.judge.adapters import DummyAdapter, ExternalProcessAdapter, HTTPAdapter
    from modules.judge.fitness import fold_scores, DEFAULT_WEIGHTS

def load_tasks(path: str):
    p = Path(path)
    if not p.exists():
        return [{"id":"echo-1","input":"ping","expected":{"contains":["p"]}}]
    return json.loads(p.read_text(encoding="utf-8"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--adapter", choices=["dummy","external","http"], default="dummy")
    ap.add_argument("--cmd")
    ap.add_argument("--url")
    ap.add_argument("--tasks", default="configs/evojudge_tasks.json")
    args = ap.parse_args()

    if args.adapter == "dummy":
        adapter = DummyAdapter()
    elif args.adapter == "external":
        if not args.cmd:
            ap.error("--cmd required for external")
        adapter = ExternalProcessAdapter(shlex.split(args.cmd))
    else:
        if not args.url:
            ap.error("--url required for http")
        adapter = HTTPAdapter(args.url)

    cfg = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    tasks = load_tasks(args.tasks)
    per = [adapter.evaluate(cfg, t) for t in tasks]
    agg = fold_scores(per, DEFAULT_WEIGHTS)
    print(json.dumps({"metrics": agg, "per_task": per}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()