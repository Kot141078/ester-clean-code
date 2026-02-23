# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _slice(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = text.find(end_marker, start)
    if end < 0:
        end = len(text)
    return text[start:end]


def main() -> int:
    agent_tool_path = (ROOT / "tools" / "agent_create.py").resolve()
    runtime_path = (ROOT / "modules" / "agents" / "runtime.py").resolve()

    tool_text = _read(agent_tool_path)
    runtime_text = _read(runtime_path)
    runtime_create_block = _slice(runtime_text, "def create_agent(", "\ndef spawn_agent(")

    checks: Dict[str, bool] = {
        "tool_exists": bool(tool_text),
        "runtime_exists": bool(runtime_text),
        "tool_uses_garage_create": "from modules.garage.templates import create_agent_from_template" in tool_text,
        "tool_avoids_runtime_import": "from modules.agents import runtime" not in tool_text,
        "runtime_warns_once": "LEGACY agents.runtime used; routed to Garage templates (canonical)." in runtime_text,
        "runtime_routes_to_garage": "_garage_create_agent_from_template(" in runtime_create_block,
        "runtime_no_direct_id_generation": ("uuid.uuid4()" not in runtime_create_block),
    }

    failures: List[str] = [k for k, ok in checks.items() if not bool(ok)]
    out = {
        "ok": len(failures) == 0,
        "checks": checks,
        "failures": failures,
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
