# scripts/install_rules_triggers.py
# -*- coding: utf-8 -*-
"""scripts/install_rules_triggers.py - ustanovka triggerov dlya YAML-avtomatizatsiy.

Zapusk:
  python scripts/install_rules_triggers.py

Action:
  - chitaet YAML iz standartnykh putey (rule_engine.load_rules)
  - register zadachi planirovschika po vsem automations (install_automation_triggers)
  - pechataet kratkiy otchet JSON v STDOUT"""
from __future__ import annotations

import json

from rule_engine import install_automation_triggers, load_rules
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main() -> int:
    bundle = load_rules()
    res = install_automation_triggers(bundle)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())