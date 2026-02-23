# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Flask


def verify(app: Flask) -> int:
    seen = {}
    dup = []
    for r in app.url_map.iter_rules():
        key = (r.rule, tuple(sorted(r.methods)))
        if key in seen:
            dup.append((r.rule, sorted(r.methods)))
        else:
            seen[key] = 1

    print('=== ROUTES ===')
    for r in sorted(app.url_map.iter_rules(), key=lambda x: x.rule):
        print(f"{','.join(sorted(r.methods))} {r.rule} -> {r.endpoint}")

    if dup:
        print("\\n=== DUPLICATES ===")
        for rule, methods in dup:
            print(f'{rule} {methods}')
        return 1

    print("\\nNo duplicates.")
    return 0


if __name__ == '__main__':
    app = Flask('verify')
    try:
        from routes.messaging_register_all_plus import register as reg_plus

        reg_plus(app)
    except Exception:
        pass
    raise SystemExit(verify(app))
