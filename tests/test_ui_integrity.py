# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.diag_templates_routes import analyze_project


class TestUIIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = ROOT

    def test_broken_url_for_is_zero(self) -> None:
        report = analyze_project(self.root)
        broken = report.get("broken_url_for", [])
        self.assertEqual(broken, [], f"broken url_for found: {broken}")

    def test_critical_routes_collision_free(self) -> None:
        report = analyze_project(self.root)
        collisions = report.get("route_collisions", [])
        critical = {
            ("/", "GET"),
            ("/_alias/portal", "GET"),
            ("/_alias/portal/health", "GET"),
            ("/_alias/favicon.ico", "GET"),
            ("/_alias/favicon/ping", "GET"),
            ("/_jwt/status", "GET"),
            ("/admin/backup", "GET"),
            ("/admin/backup/import", "POST"),
        }
        found = {
            (str(item.get("rule", "")), str(item.get("method", "")).upper())
            for item in collisions
            if (str(item.get("rule", "")), str(item.get("method", "")).upper()) in critical
        }
        self.assertEqual(found, set(), f"critical collisions found: {sorted(found)}")


if __name__ == "__main__":
    unittest.main()
