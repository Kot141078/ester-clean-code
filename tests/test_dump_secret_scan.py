# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCANNER_PATH = PROJECT_ROOT / "tools" / "dump_secret_scan.py"


def _run_scan(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-B", str(SCANNER_PATH), "--path", str(path)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    return int(proc.returncode), proc.stdout


def _load_scanner_module():
    spec = importlib.util.spec_from_file_location("dump_secret_scan_local", str(SCANNER_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError("scanner_spec_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


class TestDumpSecretScan(unittest.TestCase):
    def test_detects_openai_key_and_redacts_output(self) -> None:
        token = "sk-" + ("A" * 24) + "9Z9Z"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dump.txt"
            path.write_text(f"token={token}\n", encoding="utf-8")

            rc, stdout = _run_scan(path)
            self.assertEqual(rc, 2)
            payload = json.loads(stdout)
            self.assertFalse(payload.get("ok"))
            self.assertEqual(payload.get("exit_code"), 2)
            self.assertTrue(any(m.get("type") == "openai_sk" for m in payload.get("matches", [])))
            self.assertNotIn(token, stdout)
            token_tail = token[len(token) - 4 :]
            self.assertIn(token_tail, stdout)

    def test_passes_on_safe_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "safe.txt"
            path.write_text("hello world\nno secrets here\n", encoding="utf-8")

            rc, stdout = _run_scan(path)
            self.assertEqual(rc, 0)
            payload = json.loads(stdout)
            self.assertTrue(payload.get("ok"))
            self.assertEqual(payload.get("matches_total"), 0)

    def test_mask_preserves_last4(self) -> None:
        module = _load_scanner_module()
        value = "sk-" + ("B" * 20) + "1a2B"
        masked = module.mask_secret(value)
        self.assertTrue(masked.endswith("1a2B"))
        self.assertIn("***", masked)
        self.assertNotEqual(masked, value)


if __name__ == "__main__":
    unittest.main()
