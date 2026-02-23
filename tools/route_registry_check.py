# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from routes.route_registry import get_route_modules

    mods = get_route_modules(strict=True)
    required = {"routes.dreams_routes", "routes.metrics_prom", "routes.runtime_ab_routes"}
    missing = sorted(required - set(mods))
    if missing:
        print("route_registry_check: FAIL missing required modules:", missing)
        return 2

    reg = ROOT / "register_all.py"
    if reg.exists():
        text = reg.read_text(encoding="utf-8-sig", errors="replace")
        if re.search(r"\broute_modules\s*:\s*Sequence\s*\[\s*str\s*\]\s*=\s*\[", text):
            print("route_registry_check: FAIL register_all.py still defines typed route_modules list")
            return 2
        if re.search(r"\broute_modules\s*=\s*\[", text):
            print("route_registry_check: FAIL register_all.py still defines inline route_modules list")
            return 2

    print("route_registry_check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
