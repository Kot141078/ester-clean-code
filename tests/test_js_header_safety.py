# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestJsHeaderSafety(unittest.TestCase):
    def test_diag_js_header_safety(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                "tools/diag_js_header_safety.py",
                "--root",
                str(PROJECT_ROOT),
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + "\n" + proc.stderr)

        payload = json.loads((proc.stdout or "{}").strip() or "{}")
        self.assertTrue(payload.get("ok"), msg=proc.stdout)
        self.assertEqual(payload.get("exit_code"), 0)


if __name__ == "__main__":
    unittest.main()
