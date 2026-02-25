# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import sys
# Ensure project root on sys.path for both "ester.*" and "modules.*" layouts
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

"""CLI dlya work s banditom.
Primery:
  python tools/bandit_cli.py init --name judge --arms configs/arms.json
  python tools/bandit_cli.py pull --name judge --algo ucb1 --step 10
  python tools/bandit_cli.py update --name judge --arm-id cfgA --reward 0.8
  python tools/bandit_cli.py stage --name judge --policy configs/policy.json"""
import argparse, json
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Flexible imports
try:
    from ester.modules.meta import bandit  # type: ignore
except Exception:
    from modules.meta import bandit

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--name", required=True)
    p_init.add_argument("--arms", required=True, help="JSON list of arms")

    p_pull = sub.add_parser("pull")
    p_pull.add_argument("--name", required=True)
    p_pull.add_argument("--algo", choices=["ucb1","thompson"], default="ucb1")
    p_pull.add_argument("--step", type=int, default=1)

    p_upd = sub.add_parser("update")
    p_upd.add_argument("--name", required=True)
    p_upd.add_argument("--arm-id", required=True)
    p_upd.add_argument("--reward", type=float, required=True)
    p_upd.add_argument("--threshold", type=float, default=0.5)

    p_stage = sub.add_parser("stage")
    p_stage.add_argument("--name", required=True)
    p_stage.add_argument("--policy", required=True)

    args = ap.parse_args()

    if args.cmd == "init":
        arms = json.loads(Path(args.arms).read_text(encoding="utf-8"))
        out = bandit.init(args.name, arms)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if args.cmd == "pull":
        if args.algo == "ucb1":
            arm = bandit.pull_ucb1(args.name, step=args.step)
        else:
            arm = bandit.pull_thompson(args.name)
        print(json.dumps({"ok": True, "arm": arm}, ensure_ascii=False, indent=2))
        return

    if args.cmd == "update":
        out = bandit.update(args.name, arm_id=args.arm_id, reward=args.reward, threshold=args.threshold)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if args.cmd == "stage":
        policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
        out = bandit.stage_meta_policy(policy)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

if __name__ == "__main__":
    main()