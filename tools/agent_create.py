# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.garage.templates import create_agent_from_template

_LEGACY_ALIAS_TO_TEMPLATE = {
    "archivist": "archivist.v1",
    "builder": "builder.v1",
    "reviewer": "reviewer.v1",
}


def _resolve_template_id(raw: str) -> str:
    value = str(raw or "").strip().lower()
    if not value:
        return "builder.v1"
    mapped = _LEGACY_ALIAS_TO_TEMPLATE.get(value)
    if mapped:
        return mapped
    if value in set(_LEGACY_ALIAS_TO_TEMPLATE.values()):
        return value
    if value.endswith(".v1"):
        return value
    return value


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Create agent via Garage templates (canonical factory).")
    ap.add_argument("template_pos", nargs="?", default="", help="legacy alias or template id")
    ap.add_argument("--template", default="", help="garage template id (or legacy alias)")
    ap.add_argument("--name", default="", help="optional display name")
    ap.add_argument("--goal", default="", help="optional goal override")
    ap.add_argument("--owner", default="", help="optional owner override")
    ap.add_argument("--dry-run", action="store_true", help="render only; do not create agent files")
    ap.add_argument("--enable-oracle", action="store_true", help="enable oracle actions for template")
    ap.add_argument("--enable-comm", action="store_true", help="enable comm actions for template")
    ap.add_argument("--window-id", default="", help="required when --enable-comm is set")
    args = ap.parse_args(argv)

    template_input = str(args.template or args.template_pos or "builder").strip()
    template_id = _resolve_template_id(template_input)

    over = {
        "enable_oracle": bool(args.enable_oracle),
        "enable_comm": bool(args.enable_comm),
    }
    if str(args.name or "").strip():
        over["name"] = str(args.name).strip()
    if str(args.goal or "").strip():
        over["goal"] = str(args.goal).strip()
    if str(args.owner or "").strip():
        over["owner"] = str(args.owner).strip()
    if str(args.window_id or "").strip():
        over["window_id"] = str(args.window_id).strip()

    rep = create_agent_from_template(template_id, over, dry_run=bool(args.dry_run))
    out = {
        "ok": bool(rep.get("ok")),
        "template_id": str(rep.get("template_id") or template_id),
        "dry_run": bool(rep.get("dry_run")) if rep.get("ok") else bool(args.dry_run),
        "created": bool(rep.get("created")),
        "agent_id": str(rep.get("agent_id") or ""),
        "path": str(rep.get("path") or ""),
    }
    if rep.get("ok"):
        if rep.get("plan_path"):
            out["plan_path"] = str(rep.get("plan_path") or "")
        if rep.get("readme_path"):
            out["readme_path"] = str(rep.get("readme_path") or "")
        out["allowed_actions"] = list(rep.get("allowed_actions") or [])
        if rep.get("template_missing_actions"):
            out["template_missing_actions"] = list(rep.get("template_missing_actions") or [])
        if rep.get("template_disabled_by_policy"):
            out["template_disabled_by_policy"] = list(rep.get("template_disabled_by_policy") or [])
    else:
        out["error"] = str(rep.get("error") or "create_failed")
        out["detail"] = str(rep.get("detail") or "")

    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
