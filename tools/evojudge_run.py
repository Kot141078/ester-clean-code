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

# Flexible imports: prefer "ester.modules", fallback to "modules"
try:
    from ester.modules.judge.evo_judge import EvoJudgeRunner  # type: ignore
    from ester.modules.judge.adapters import DummyAdapter, ExternalProcessAdapter, HTTPAdapter  # type: ignore
except Exception:
    from modules.judge.evo_judge import EvoJudgeRunner
    from modules.judge.adapters import DummyAdapter, ExternalProcessAdapter, HTTPAdapter

def load_tasks(path: str):
    p = Path(path)
    if not p.exists():
        return [{"id":"echo-1","input":"ping","expected":{"contains":["p"]}}]
    return json.loads(p.read_text(encoding="utf-8"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=["dummy","external","http"], default="dummy")
    ap.add_argument("--cmd")
    ap.add_argument("--url")
    ap.add_argument("--tasks", default="configs/evojudge_tasks.json")
    ap.add_argument("--label", default="default")
    ap.add_argument("--seed", type=int, default=123)
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

    tasks = load_tasks(args.tasks)
    runner = EvoJudgeRunner(adapter=adapter, tasks=tasks, label=args.label, seed=args.seed)
    out = runner.run()
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()