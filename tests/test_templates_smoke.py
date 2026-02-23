# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from pathlib import Path

from tools.diag_templates_routes import analyze_project


class TestTemplatesSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_templates_directory_exists(self) -> None:
        self.assertTrue((self.root / "templates").is_dir(), "templates directory is missing")

    def test_portal_guess_exists(self) -> None:
        report = analyze_project(self.root)
        portal_guess = str(report.get("portal_guess", "")).strip()
        self.assertTrue(portal_guess, "portal_guess is empty")


if __name__ == "__main__":
    unittest.main()

