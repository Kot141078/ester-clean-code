# -*- coding: utf-8 -*-
"""tools/show_experience_profile.py - profilya opyta Ester.

Name:
- Safely prochitat tekuschiy profil opyta bez perezapisi dannykh.
- Check it out, what do you think about it?

Mosty:
- Yavnyy: ispolzuet modules.memory.experience.build_experience_profile().
- Skrytyy #1: opiraetsya na dannye sna / reflections (sleep → reflection → experience).
- Skrytyy #2: sluzhit istochnikom dlya thinking.experience_context_adapter (ruchnaya proverka).

Zemnoy abzats:
Podobno nevrologu, kotoryy smotrit snimok mozga posle sna, skript pechataet snimok
"dolgovremennoy pamyati" Ester: skolko insaytov, kakie temy, bez lishnego vmeshatelstva.

Zapusk:
    python tools/show_experience_profile.py"""

import json
import sys
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _ensure_project_root() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

def main() -> None:
    _ensure_project_root()
    try:
        from modules.memory import experience  # type: ignore
    except Exception as e:  # pragma: no cover
        print(json.dumps(
            {"ok": False, "error": f"import_error: {e!s}"},
            ensure_ascii=False,
            indent=2,
        ))
        sys.exit(1)

    try:
        profile = experience.build_experience_profile()
    except Exception as e:  # pragma: no cover
        profile = {"ok": False, "error": f"profile_error: {e!s}"}

    out = {
        "ok": bool(profile.get("ok", False)),
        "profile": profile,
    }

    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()