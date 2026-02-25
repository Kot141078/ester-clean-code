# -*- coding: utf-8 -*-
"""routes/ops_probe_usb.py - health-proba USB-agenta.

Route:
  • GET /ops/probe/usb - {"ok": bool, "reason": str, "p95": float, "age": int, ...}

ENV threshold (optional):
  • ESTER_USB_HEALTH_MAX_P95=5 - threshold p95 (sek)
  • ESTER_USB_HEALTH_MAX_AGE=86400 - max. vozrast poslednego sobytiya (sek)

Mosty:
- Yavnyy (Ashbi ↔ Ekspluatatsiya): binarnyy “zdorov/ne zdorov” po nablyudaemym velichinam.
- Skrytyy 1 (Infoteoriya ↔ Diagnostika): lakonichnyy JSON dlya chelovek/mashina.
- Skrytyy 2 (Logika ↔ Bezopasnost): porogi - yavnye, bez skrytykh said-effektov.

Zemnoy abzats:
Health-endpoint goditsya dlya Kubernetes/LB-prob: esli pulse redkiy or p95 velik - soobschaem “degraded/false”.

# c=a+b"""
from __future__ import annotations

import os
import time
from flask import Blueprint, jsonify
from metrics.usb_agent_stats import USBStats  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ops_probe_usb = Blueprint("ops_probe_usb", __name__)

def _to_i(env_key: str, default: int) -> int:
    try:
        return int(os.getenv(env_key, str(default)).strip())
    except Exception:
        return default

@bp_ops_probe_usb.get("/ops/probe/usb")
def ops_probe_usb():
    s = USBStats()
    snap = s.snapshot()
    now = int(time.time())
    age = max(0, now - int(snap.get("last_ts") or 0))
    p95 = float(snap.get("p95") or 0.0)

    thr_p95 = _to_i("ESTER_USB_HEALTH_MAX_P95", 5)
    thr_age = _to_i("ESTER_USB_HEALTH_MAX_AGE", 86400)

    ok = (p95 <= thr_p95) and (age <= thr_age)
    reason = []
    if p95 > thr_p95:
        reason.append(f"p95>{thr_p95}s")
    if age > thr_age:
        reason.append(f"age>{thr_age}s")
    if not reason:
        reason.append("ok")

    return jsonify({
        "ok": bool(ok),
        "reason": ",".join(reason),
        "p95": p95,
        "age": age,
        "counts": {"ok": snap.get("ok", 0), "err": snap.get("err", 0), "window": snap.get("count", 0)},
        "path": snap.get("path"),
        "ts": snap.get("last_ts"),
    })
# c=a+b


def register(app):
    app.register_blueprint(bp_ops_probe_usb)
    return app