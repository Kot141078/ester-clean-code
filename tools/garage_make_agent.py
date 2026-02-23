# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage.templates import create_agent_from_template


def create_from_template(
    *,
    template_id: str,
    name: str = "",
    goal: str = "",
    owner: str = "ester",
    enable_oracle: bool = False,
    enable_comm: bool = False,
    dry_run: bool = False,
    window_id: str = "",
) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {
        "name": str(name or ""),
        "goal": str(goal or ""),
        "owner": str(owner or "ester"),
        "enable_oracle": bool(enable_oracle),
        "enable_comm": bool(enable_comm),
        "window_id": str(window_id or ""),
    }
    return create_agent_from_template(str(template_id or ""), overrides=overrides, dry_run=bool(dry_run))


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Create Garage agent from template pack v1.")
    ap.add_argument("--template", required=True, help="template id, e.g. builder.v1")
    ap.add_argument("--name", default="", help="agent name override")
    ap.add_argument("--goal", default="", help="goal override")
    ap.add_argument("--owner", default="ester", help='owner override (default: "ester")')
    ap.add_argument("--enable-oracle", action="store_true", help="enable oracle policy (default: OFF)")
    ap.add_argument("--enable-comm", action="store_true", help="enable comm policy (default: OFF)")
    ap.add_argument("--dry-run", action="store_true", help="mark creation as dry-run metadata")
    ap.add_argument("--print-plan", action="store_true", help="include generated plan in output")
    ap.add_argument("--window-id", default="", help="oracle window id when --enable-oracle is used")
    args = ap.parse_args(argv)

    rep = create_from_template(
        template_id=str(args.template or ""),
        name=str(args.name or ""),
        goal=str(args.goal or ""),
        owner=str(args.owner or "ester"),
        enable_oracle=bool(args.enable_oracle),
        enable_comm=bool(args.enable_comm),
        dry_run=bool(args.dry_run),
        window_id=str(args.window_id or ""),
    )

    out = dict(rep)
    if not bool(args.print_plan):
        out.pop("plan", None)
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if bool(rep.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

