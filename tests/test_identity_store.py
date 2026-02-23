# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import unittest

from modules.state.identity_store import load_anchor, load_profile, save_anchor, save_profile


class TestIdentityStore(unittest.TestCase):
    def test_save_load_profile_and_anchor_utf8(self) -> None:
        old = os.environ.get("ESTER_STATE_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["ESTER_STATE_DIR"] = tmp
                saved = save_profile({"human_name": "Owner", "language": "ru", "timezone": "UTC"})
                self.assertEqual(saved["human_name"], "Owner")

                anchor_text = "Anchor: nablyudaem, pereosmyslyaem, deystvuem."
                save_anchor(anchor_text)

                loaded_profile = load_profile()
                loaded_anchor = load_anchor()
                self.assertEqual(loaded_profile["human_name"], "Owner")
                self.assertEqual(loaded_profile["language"], "ru")
                self.assertEqual(loaded_profile["timezone"], "UTC")
                self.assertEqual(loaded_anchor, anchor_text)
        finally:
            if old is None:
                os.environ.pop("ESTER_STATE_DIR", None)
            else:
                os.environ["ESTER_STATE_DIR"] = old


if __name__ == "__main__":
    unittest.main()

