# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestUISmokeStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def _diag_report(self) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "ui_report.json"
            md_path = Path(tmp) / "UI_REPORT.md"
            cmd = [
                sys.executable,
                "-B",
                str(self.root / "tools" / "diag_templates_routes.py"),
                "--project",
                str(self.root),
                "--json-out",
                str(json_path),
                "--md-out",
                str(md_path),
            ]
            proc = subprocess.run(cmd, cwd=str(self.root), capture_output=True, text=True, check=False)
            self.assertEqual(
                proc.returncode,
                0,
                msg=f"diag_templates_routes failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
            )
            return json.loads(json_path.read_text(encoding="utf-8"))

    def test_admin_routes_are_unique(self) -> None:
        report = self._diag_report()
        collisions = report.get("route_collisions", [])
        bad = {
            (c.get("rule"), c.get("method"))
            for c in collisions
            if (c.get("rule"), c.get("method")) in {("/admin", "GET"), ("/admin/portal", "GET")}
        }
        self.assertEqual(bad, set(), f"critical route collisions found: {sorted(bad)}")

    def test_tmp_ui_server_file_absent(self) -> None:
        tmp_path = self.root / "tools" / "_tmp_ui_server.py"
        self.assertFalse(tmp_path.exists(), "tools/_tmp_ui_server.py must not exist")


if __name__ == "__main__":
    unittest.main()

