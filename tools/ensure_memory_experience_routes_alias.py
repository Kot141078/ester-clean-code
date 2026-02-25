# -*- coding: utf-8 -*-
"""tools/ensure_memory_experience_routes_alias.py

Goryachiy fiks: garantiruet nalichie routes/memory_experience_routes_alias.py
i korrektnogo paketa routes, ne trogaya suschestvuyuschie fayly, esli oni uzhe est.

Invariance:
- Drop-in.
- Ne perezapisyvaet suschestvuyuschiy alias, tolko sozdaet pri otsutstvii.
- Sozdaet routes/__init__.py, esli ego ne bylo (safe)."""

from __future__ import annotations

from pathlib import Path

ALIAS_MODULE = "memory_experience_routes_alias.py"

ALIAS_SOURCE = '''# -*- coding: utf-8 -*-\n"""routes/memory_experience_routes_alias.py

HTTP-alias dlya chteniya profilya opyta Ester.

Invariance:
- Drop-in.
- Ispolzuet suschestvuyuschiy layer `modules.memory.experience`.
- Tolko chtenie, bez pobochnykh effektov.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.memory import experience # type: ignore
except Exception as e: # pragma: no cover
    _experience_import_error = e
    experience = None # type: ignore
else:
    _experience_import_error = None

bp = Blueprint("memory_experience_alias", __name__)


@bp.route("/memory/experience/profile", methods=["GET"])
def memory_experience_profile():
    """Vernut tekuschiy profil opyta."""
    if experience is None: # pragma: no cover
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"import_error: {_experience_import_error!s}",
                }
            ),
            500,
        )

    try:
        profile = experience.build_experience_profile()
    except Exception as e: # pragma: no cover
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"profile_error: {e!s}",
                }
            ),
            500,
        )

    return jsonify(
        {
            "ok": bool(profile.get("ok", False)),
            "profile": profile,
        }
    )'''


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    routes_dir = root / "routes"
    if not routes_dir.exists():
        routes_dir.mkdir(parents=True, exist_ok=True)
        print(f"[ok] created {routes_dir}")

    init_path = routes_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text(
            "# -*- coding: utf-8 -*-\n# routes package init\n",
            encoding="utf-8",
        )
        print(f"[ok] created {init_path}")
    else:
        print(f"[ok] {init_path} exists")

    alias_path = routes_dir / ALIAS_MODULE
    if not alias_path.exists():
        alias_path.write_text(ALIAS_SOURCE, encoding="utf-8")
        print(f"[ok] created {alias_path}")
    else:
        print(f"[ok] {alias_path} already exists")


if __name__ == "__main__":
    main()