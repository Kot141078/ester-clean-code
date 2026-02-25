# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import sys
# Ensure project root on sys.path for both "ester.*" and "modules.*" layouts
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

"""CLI dlya work s trials (bez veba).
Primery:
  python tools/trials_cli.py create --id nightly --spec configs/evojudge_tasks.json
  python tools/trials_cli.py run --id nightly --adapter dummy --tasks configs/evojudge_tasks.json"""
import argparse, json, shlex
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Flexible imports
try:
    from ester.modules.meta import trials  # type: ignore
    from ester.modules.judge.adapters import DummyAdapter, ExternalProcessAdapter, HTTPAdapter  # type: ignore
except Exception:
    from modules.meta import trials
    from modules.judge.adapters import DummyAdapter, ExternalProcessAdapter, HTTPAdapter

def load_tasks(path: str):
    p = Path(path)
    if not p.exists():
        return [{"id":"echo-1","input":"ping","expected":{"contains":["p"]}}]
    return json.loads(p.read_text(encoding="utf-8"))

def mk_adapter(kind: str, cmd: str|None, url: str|None):
    kind = (kind or "dummy").lower()
    if kind == "dummy":
        return DummyAdapter()
    if kind == "external":
        if not cmd: raise SystemExit("--cmd required for external")
        return ExternalProcessAdapter(shlex.split(cmd))
    if kind == "http":
        if not url: raise SystemExit("--url required for http")
        return HTTPAdapter(url)
    raise SystemExit("unknown adapter")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_create = sub.add_parser("create")
    ap_create.add_argument("--id", required=True)
    ap_create.add_argument("--spec", required=True, help="JSON-fayl so spekami (svobodnaya forma)")

    ap_run = sub.add_parser("run")
    ap_run.add_argument("--id", required=True)
    ap_run.add_argument("--adapter", choices=["dummy","external","http"], default="dummy")
    ap_run.add_argument("--cmd")
    ap_run.add_argument("--url")
    ap_run.add_argument("--tasks", required=True)
    ap_run.add_argument("--profile", help="JSON profil konfiga", default=None)

    args = ap.parse_args()

    if args.cmd == "create":
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        out = trials.create_spec(args.id, spec)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if args.cmd == "run":
        adapter = mk_adapter(args.adapter, args.cmd, args.url)
        tasks = load_tasks(args.tasks)
        config = json.loads(Path(args.profile).read_text(encoding="utf-8")) if args.profile else {}
        results = []
        for t in tasks:
            res = trials.run_episode(args.id, adapter=adapter, task=t, config=config)
            results.append(res)
        print(json.dumps({"ok": True, "episodes": len(results)}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()