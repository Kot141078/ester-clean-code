# -*- coding: utf-8 -*-
"""
tests/test_rulehub_http.py — minimalnye unit-testy HTTP-marshrutov (stdlib only).

Testiruem:
  • /rulehub/state, /rulehub/last, /rulehub/toggle
  • /metrics/mind, /metrics/video
  • /portal/widgets/mind, /portal/widgets/videos
  • /ingest/video/index/state, /health/video/selfcheck
  • /thinking/presets, /rulehub/export.{ndjson,csv}

Mosty:
- Yavnyy: (Nablyudaemost ↔ Kachestvo) testy — strakhovka integratsiy bez vneshnikh freymvorkov.
- Skrytyy #1: (Infoteoriya ↔ Diagnostika) proveryaem validnost formatov (JSON/HTML/Prometheus/CSV).
- Skrytyy #2: (Kibernetika ↔ Kontrol) round-trip toggle demonstriruet bezopasnoe upravlenie RuleHub.

Zemnoy abzats:
Eto «dezhurnyy nabor» dlya nochnogo operatora: prognat i uvidet, gde zagorelas lampa.

# c=a+b
"""
from __future__ import annotations

import json
import os
import unittest
import urllib.request
import urllib.error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = os.getenv("ESTER_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = 5.0

def _req(path: str, data=None, method="GET"):
    url = BASE + path
    headers = {}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.getcode(), r.read().decode("utf-8", errors="ignore"), dict(r.headers.items())

class TestRuleHubHTTP(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Proverim dostupnost bazovogo endpointa; esli net — propustim vse testy
        try:
            code, body, hdr = _req("/rulehub/state")
            assert code == 200
        except Exception as e:
            raise unittest.SkipTest(f"Server not reachable at {BASE}: {e}")

    def test_rulehub_state_json(self):
        code, body, _ = _req("/rulehub/state")
        self.assertEqual(code, 200)
        j = json.loads(body)
        self.assertIn("ok", j)
        self.assertIn("enabled", j)

    def test_rulehub_toggle_roundtrip(self):
        code, body, _ = _req("/rulehub/state")
        self.assertEqual(code, 200)
        enabled = json.loads(body).get("enabled", False)
        # toggle
        code2, body2, _ = _req("/rulehub/toggle", {"enabled": 0 if enabled else 1}, "POST")
        self.assertEqual(code2, 200)
        # restore
        _req("/rulehub/toggle", {"enabled": 1 if enabled else 0}, "POST")

    def test_metrics_mind(self):
        code, body, _ = _req("/metrics/mind")
        self.assertEqual(code, 200)
        self.assertIn("mind_last_timestamp_seconds", body)

    def test_metrics_video(self):
        code, body, _ = _req("/metrics/video")
        self.assertEqual(code, 200)
        self.assertIn("video_summary_chars_total", body)

    def test_widgets_html(self):
        code, body, hdr = _req("/portal/widgets/mind?limit=1")
        self.assertEqual(code, 200)
        self.assertIn("<div", body.lower())
        code, body, hdr = _req("/portal/widgets/videos?limit=1")
        self.assertEqual(code, 200)
        self.assertIn("<div", body.lower())

    def test_index_state_and_health(self):
        code, body, _ = _req("/ingest/video/index/state")
        self.assertEqual(code, 200)
        j = json.loads(body)
        self.assertIn("ok", j)
        self.assertIn("queue_size", j)
        code, body, _ = _req("/health/video/selfcheck")
        self.assertEqual(code, 200)
        j = json.loads(body)
        self.assertIn("bins", j)

    def test_presets_and_export(self):
        code, body, _ = _req("/thinking/presets")
        self.assertEqual(code, 200)
        j = json.loads(body)
        self.assertIn("presets", j)
        # NDJSON
        code, body, _ = _req("/rulehub/export.ndjson?limit=2")
        self.assertEqual(code, 200)
        self.assertGreaterEqual(len(body.splitlines()), 0)
        # CSV
        code, body, hdr = _req("/rulehub/export.csv?limit=2")
        self.assertEqual(code, 200)
        self.assertTrue(body.splitlines()[0].lower().startswith("ts,"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
