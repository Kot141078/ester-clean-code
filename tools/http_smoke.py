#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/http_smoke.py — prostoy oflayn smoke-test HTTP-marshrutov Ester (bez storonnikh bibliotek).

Chto delaet:
  • Proveryaet klyuchevye endpointy VideoIngestCore i MindRuleHub.
  • Umeet bezopasno pereklyuchat RuleHub (toggle) i vozvraschat v iskhodnoe sostoyanie.
  • Pechataet chelovekochitaemyy otchet ili JSON (flag --json).

Mosty:
- Yavnyy: (Nablyudaemost ↔ Ekspluatatsiya) edinaya komanda dlya proverki «dyshit li kontur myshleniya i video».
- Skrytyy #1: (Infoteoriya ↔ Diagnostika) validiruem formaty otvetov: JSON/HTML/Prometheus.
- Skrytyy #2: (Kibernetika ↔ Kontrol) toggle RuleHub — proverka «voli» vklyuchat nablyudaemost bez restartov.

Zemnoy abzats:
Eto «karmannyy tester u tekhnika»: bystro oboyti pult, lampy i tablo; esli chto — schelknut tumbler i proverit reaktsiyu.

# c=a+b
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = os.getenv("ESTER_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

def _req(path: str, method: str = "GET", data: Optional[dict] = None, timeout: float = 5.0) -> Tuple[int, str, Dict[str, str]]:
    url = BASE + path
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", errors="ignore")
            return r.getcode(), txt, dict(r.headers.items())
    except urllib.error.HTTPError as e:
        try:
            txt = e.read().decode("utf-8", errors="ignore")
        except Exception:
            txt = str(e)
        return e.code, txt, dict(e.headers.items()) if e.headers else {}
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}", {}

def _json_ok(txt: str) -> bool:
    try:
        j = json.loads(txt)
        return isinstance(j, dict) and "ok" in j
    except Exception:
        return False

def _prom_ok(txt: str, must_contain: List[str]) -> bool:
    return all(s in txt for s in must_contain)

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="pechat rezultata v JSON")
    args = ap.parse_args(argv)

    checks = []

    def add(name: str, path: str, expect: str, ok: bool, code: int, note: str = ""):
        checks.append({"name": name, "path": path, "expect": expect, "ok": bool(ok), "code": code, "note": note})

    # 1) RuleHub state
    code, body, hdr = _req("/rulehub/state")
    add("rulehub_state", "/rulehub/state", "application/json", code == 200 and _json_ok(body), code)

    # Save current enabled and toggle round-trip
    was_enabled = False
    try:
        was_enabled = json.loads(body).get("enabled", False)
    except Exception:
        pass
    # toggle on
    code2, body2, _ = _req("/rulehub/toggle", "POST", {"enabled": 1 if not was_enabled else 0})
    add("rulehub_toggle", "/rulehub/toggle", "toggle ok", code2 == 200 and '"ok": true' in body2.lower(), code2)
    # restore
    if code2 == 200:
        _req("/rulehub/toggle", "POST", {"enabled": 1 if was_enabled else 0})

    # 2) RuleHub last
    code, body, hdr = _req("/rulehub/last?limit=5")
    add("rulehub_last", "/rulehub/last?limit=5", "application/json", code == 200 and _json_ok(body), code)

    # 3) Mind metrics
    code, body, hdr = _req("/metrics/mind")
    add("metrics_mind", "/metrics/mind", "prometheus", code == 200 and _prom_ok(body, ["mind_last_timestamp_seconds"]), code)

    # 4) Video metrics
    code, body, hdr = _req("/metrics/video")
    add("metrics_video", "/metrics/video", "prometheus", code == 200 and _prom_ok(body, ["video_summary_chars_total"]), code)

    # 5) Widgets (HTML)
    code, body, hdr = _req("/portal/widgets/mind?limit=1")
    add("widget_mind", "/portal/widgets/mind?limit=1", "text/html", code == 200 and "<div" in body.lower(), code)

    code, body, hdr = _req("/portal/widgets/videos?limit=1")
    add("widget_video", "/portal/widgets/videos?limit=1", "text/html", code == 200 and "<div" in body.lower(), code)

    # 6) Index state / health
    code, body, hdr = _req("/ingest/video/index/state")
    add("index_state", "/ingest/video/index/state", "application/json", code == 200 and _json_ok(body), code)

    code, body, hdr = _req("/health/video/selfcheck")
    add("video_selfcheck", "/health/video/selfcheck", "application/json", code == 200 and _json_ok(body), code)

    # 7) Presets/Export
    code, body, hdr = _req("/thinking/presets")
    add("presets_list", "/thinking/presets", "application/json", code == 200 and _json_ok(body), code)

    code, body, hdr = _req("/rulehub/export.ndjson?limit=3")
    add("export_ndjson", "/rulehub/export.ndjson?limit=3", "ndjson", code == 200 and "\n" in body, code)

    code, body, hdr = _req("/rulehub/export.csv?limit=3")
    add("export_csv", "/rulehub/export.csv?limit=3", "text/csv", code == 200 and "status" in body.splitlines()[0].lower(), code)

    # vyvod
    ok_total = sum(1 for c in checks if c["ok"])
    if args.json:
        print(json.dumps({"base": BASE, "ok": ok_total, "total": len(checks), "checks": checks}, ensure_ascii=False, indent=2))
    else:
        print(f"Base: {BASE}")
        for c in checks:
            mark = "OK " if c["ok"] else "ERR"
            print(f"[{mark}] {c['name']:<18} {c['path']:<40} expect={c['expect']:<14} code={c['code']}")
        print(f"Summary: {ok_total}/{len(checks)} OK")
    return 0 if ok_total == len(checks) else 1

if __name__ == "__main__":
    raise SystemExit(main())
