# -*- coding: utf-8 -*-
"""tools/force_memory_experience_routes_alias.py

Forsirovannoe sozdanie/obnovlenie routes/memory_experience_routes_alias.py.

Ispolzovanie:
  python tools/force_memory_experience_routes_alias.py

Invarianty:
- Drop-in: menyaem tolko alias-fayl i routes/__init__.py.
- Ne trogaem modules.memory.*, cascade, portal i t.p.
"""

from __future__ import annotations

from pathlib import Path


ALIAS_FILENAME = "memory_experience_routes_alias.py"

ALIAS_CODE = '''# -*- coding: utf-8 -*-
"""routes/memory_experience_routes_alias.py

HTTP-alias dlya chteniya profilya opyta Ester.

Invarianty:
- Drop-in: ne trogaem suschestvuyuschuyu arkhitekturu.
- Ispolzuem suschestvuyuschiy sloy `modules.memory.experience`.
- Tolko chtenie, bez pobochnykh effektov.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.memory import experience  # type: ignore
except Exception as e:  # pragma: no cover
    _experience_import_error = e
    experience = None  # type: ignore
else:
    _experience_import_error = None

bp = Blueprint("memory_experience_routes_alias", __name__)


@bp.route("/memory/experience/profile", methods=["GET"])
def memory_experience_profile():
    """Vernut tekuschiy profil opyta.

    Format otveta:
    {
      "ok": bool,
      "profile": {...}
    }
    """
    if experience is None:  # pragma: no cover
        return (
            jsonify({"ok": False, "error": f"import_error: {_experience_import_error!s}"}),
            500,
        )

    try:
        profile = experience.build_experience_profile()
    except Exception as e:  # pragma: no cover
        return (
            jsonify({"ok": False, "error": f"profile_error: {e!s}"}),
            500,
        )

    ok = bool(getattr(profile, "get", lambda *_: False)("ok", True)) if isinstance(profile, dict) else True

    return jsonify({"ok": ok, "profile": profile})
'''


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    routes_dir = root / "routes"
    routes_dir.mkdir(parents=True, exist_ok=True)

    init_path = routes_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text(
            "# -*- coding: utf-8 -*-\n# routes package init\n",
            encoding="utf-8",
        )
        print(f"[ok] created {init_path}")
    else:
        print(f"[ok] {init_path} exists")

    alias_path = routes_dir / ALIAS_FILENAME
    alias_path.write_text(ALIAS_CODE, encoding="utf-8")
    print(f"[ok] wrote {alias_path} (force)")


if __name__ == "__main__":
    main()