# -*- coding: utf-8 -*-
"""scripts/ester_thinking_mode.py

Mosty:
- Yavnyy: (CLI <-> thinking_profiles) - pechataet gotovye ENV-nabory dlya raznykh rezhimov.
- Skrytyy #1: (inzhener <-> .env) — daet komandy dlya PowerShell/Bash bez avtozapisi faylov.
- Skrytyy #2: (thinking_manifest <-> rezhimy) - profili sovmestimy s tem, what proveryaet manifest.

Zemnoy abzats:
Zapuskaesh:
    python -m scripts.ester_thinking_mode human_like
i poluchaesh stroki dlya PowerShell/Linux, kotorye vklyuchayut u Ester volyu, priority,
mnogokontekstnyy kaskad i treys. Nikakoy magii: ty sam reshaesh, primenyat ili net.
# c=a+b"""
from __future__ import annotations

import sys
import json
from typing import Dict

from modules.ester.thinking_profiles import list_profiles, get_profile
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _powershell_commands(env: Dict[str, str]) -> str:
    lines = []
    for k, v in env.items():
        if v is None:
            continue
        lines.append(f'$env:{k}="{v}"')
    return "\n".join(lines)


def _bash_commands(env: Dict[str, str]) -> str:
    lines = []
    for k, v in env.items():
        if v is None:
            continue
        lines.append(f'export {k}="{v}"')
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("Usage: python -m scripts.ester_thinking_mode <profile>")
        print("Profiles:", ", ".join(list_profiles()))
        print("Example:")
        print("  python -m scripts.ester_thinking_mode human_like")
        return 0

    name = sys.argv[1]
    try:
        env = get_profile(name)
    except KeyError as e:
        print(str(e), file=sys.stderr)
        print("Available profiles:", ", ".join(list_profiles()), file=sys.stderr)
        return 1

    print(f"[ester_thinking_mode] profile={name}")
    print()
    print("# ZHSION (for verification)")
    print(json.dumps(env, ensure_ascii=False, indent=2))
    print()
    print("# PowerShell (Windows)")
    print(_powershell_commands(env))
    print()
    print("# Bash (Linux/macOS)")
    print(_bash_commands(env))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())