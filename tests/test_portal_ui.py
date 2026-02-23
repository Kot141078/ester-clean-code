# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.diag_templates_routes import analyze_project


class TestPortalUIDiagnostics(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_diag_templates_routes_cli_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_json = Path(tmp) / "ui_report.json"
            out_md = Path(tmp) / "UI_REPORT.md"
            cmd = [
                sys.executable,
                "-B",
                str(self.root / "tools" / "diag_templates_routes.py"),
                "--project",
                str(self.root),
                "--json-out",
                str(out_json),
                "--md-out",
                str(out_md),
            ]
            proc = subprocess.run(cmd, cwd=str(self.root), capture_output=True, text=True, check=False)
            self.assertEqual(
                proc.returncode,
                0,
                msg=f"diag_templates_routes failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
            )
            self.assertTrue(out_json.is_file(), "ui_report.json was not created")
            self.assertTrue(out_md.is_file(), "UI_REPORT.md was not created")
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertIn("flask_render_routes", payload)
            self.assertIn("route_collisions", payload)
            self.assertFalse(
                bool((payload.get("tmp_file_guard") or {}).get("exists")),
                "tmp UI server file guard failed",
            )

    def test_missing_templates_empty_and_routes_present(self) -> None:
        report = analyze_project(self.root)
        self.assertGreater(
            len(report.get("flask_render_routes", [])),
            0,
            "flask_render_routes is empty, UI routes are not detected",
        )
        self.assertEqual(
            report.get("missing_templates", []),
            [],
            f"missing_templates is not empty: {report.get('missing_templates', [])}",
        )


if __name__ == "__main__":
    unittest.main()
