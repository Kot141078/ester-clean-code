# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from modules.settings.registry import all_settings, validate_many


class TestSettingsRegistry(unittest.TestCase):
    def test_registry_keys_unique(self) -> None:
        keys = [item.key for item in all_settings()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_validation_rejects_unknown_keys(self) -> None:
        valid, errors = validate_many({"unknown.setting": "x"})
        self.assertEqual(valid, {})
        self.assertIn("unknown.setting", errors)
        self.assertEqual(errors["unknown.setting"], "unknown_key")


if __name__ == "__main__":
    unittest.main()

