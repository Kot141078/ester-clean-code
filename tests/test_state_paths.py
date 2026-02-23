# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from modules.state.paths import resolve_state_dir


class TestStatePaths(unittest.TestCase):
    def test_resolve_state_dir_returns_path(self) -> None:
        old = os.environ.get("ESTER_STATE_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["ESTER_STATE_DIR"] = tmp
                got = resolve_state_dir()
                self.assertTrue(got.exists())
                self.assertEqual(got.resolve(), Path(tmp).resolve())
        finally:
            if old is None:
                os.environ.pop("ESTER_STATE_DIR", None)
            else:
                os.environ["ESTER_STATE_DIR"] = old


if __name__ == "__main__":
    unittest.main()

