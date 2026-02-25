# -*- coding: utf-8 -*-
"""tools/register_memory_experience_routes_alias.py

Registration HTTP-aliasa profilya opyta.

Add `routes.memory_experience_routes_alias` v data/app/extra_routes.json,
esli ego there esche net.

Invariance:
- Ne trogaem suschestvuyuschie zapisi.
- Safe in the future.
- Umeet rabotat i s formatom:
    1) ["routes.foo", ... ]
    2) { "routes": [ "routes.foo", ... ], ... }"""

import json
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


ALIAS = "routes.memory_experience_routes_alias"


def load_routes_config(cfg_path: Path):
    """Schitat config extra_routes v maximalno schadyaschem rezhime.

    Vozvraschaet: (routes: list[str], mode: str)
    mode:
      - "list" — fayl yavlyaetsya spiskom marshrutov;
      - "dict" - fayl yavlyaetsya obektom s polem "routes";
      - "new" - fayla ne bylo, sozdaem spisok."""
    if not cfg_path.exists():
        return [], "new"

    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # Damaged file: don't break it, start with a clean list.
        return [], "list"

    if isinstance(data, list):
        return data, "list"

    if isinstance(data, dict):
        routes = data.get("routes", [])
        if not isinstance(routes, list):
            routes = []
        return (data, "dict") if routes is not None else ([], "dict")

    # Unexpected format - start over as a list.
    return [], "list"


def save_routes_config(cfg_path: Path, payload, mode: str, alias: str) -> None:
    """Save the config without changing the format more than necessary."""
    if mode in ("new", "list"):
        # We simply store a list of routes.
        if isinstance(payload, dict):
            routes = payload.get("routes", [])
        else:
            routes = payload
        if not isinstance(routes, list):
            routes = []
        if alias not in routes:
            routes.append(alias)
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with cfg_path.open("w", encoding="utf-8") as f:
            json.dump(routes, f, ensure_ascii=False, indent=2)
        return

    if mode == "dict":
        # We save it as an object with the “Rute” field.
        if not isinstance(payload, dict):
            payload = {}
        routes = payload.get("routes", [])
        if not isinstance(routes, list):
            routes = []
        if alias not in routes:
            routes.append(alias)
        payload["routes"] = routes
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with cfg_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return

    # Fallback option: as a list.
    routes = []
    if isinstance(payload, list):
        routes = payload
    if alias not in routes:
        routes.append(alias)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg_path.open("w", encoding="utf-8") as f:
        json.dump(routes, f, ensure_ascii=False, indent=2)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg_path = root / "data" / "app" / "extra_routes.json"

    payload, mode = load_routes_config(cfg_path)

    # Determine if there is already an alias
    if mode == "dict" and isinstance(payload, dict):
        routes = payload.get("routes", [])
        if not isinstance(routes, list):
            routes = []
    elif isinstance(payload, list):
        routes = payload
    else:
        routes = []

    if ALIAS in routes:
        print(f"[ok] {ALIAS} already present in {cfg_path}")
        return

    save_routes_config(cfg_path, payload, mode, ALIAS)
    print(f"[ok] added {ALIAS} to {cfg_path}")


if __name__ == "__main__":
    main()