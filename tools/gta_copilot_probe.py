# -*- coding: utf-8 -*-
"""Send one sample GTA telemetry packet to local Ester backend."""
from __future__ import annotations

import argparse
import json
import time
import urllib.request


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8090/gta/ingest")
    ap.add_argument("--ask", action="store_true")
    args = ap.parse_args()

    payload = {
        "sid": "gta-v",
        "user_name": "owner",
        "ask": bool(args.ask),
        "state": {
            "ts_ms": int(time.time() * 1000),
            "wanted": 2,
            "hp": 91,
            "armor": 37,
            "in_vehicle": True,
            "vehicle": "Kuruma",
            "speed_kmh": 88.5,
            "zone": "Downtown",
            "objective": "Reach marker safely",
        },
    }

    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        args.url,
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
