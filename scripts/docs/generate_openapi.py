

### `scripts/docs/generate_openapi.py`

# -*- coding: utf-8 -*-
"""
scripts/docs/generate_openapi.py — vygruzka OpenAPI skhemy iz FastAPI-prilozheniya.

MOSTY:
- (Yavnyy) Importiruet asgi.synergy_api_v2.app i sokhranyaet openapi.json na disk.
- (Skrytyy #1) Bez setevogo zapuska, folbek: pytaetsya importirovat asgi.app_main i vzyat app ottuda.
- (Skrytyy #2) Stavit version/metadata iz app.title/version (esli est).

ZEMNOY ABZATs:
Garantiruet, chto skhema v repozitorii sootvetstvuet tekuschemu kodu — udobno dlya vneshnikh integratorov i revyu bezopasnosti.

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def load_app():
    try:
        from asgi.synergy_api_v2 import app
        return app
    except Exception:
        pass
    try:
        from asgi.app_main import app
        return app
    except Exception as e:
        print(f"ERROR: cannot import app: {e}", file=sys.stderr)
        sys.exit(2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/API/openapi.json")
    args = ap.parse_args()

    app = load_app()
    data = app.openapi()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✓ OpenAPI saved to {args.out}")

if __name__ == "__main__":
    main()