# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import tempfile
import unittest

from modules.security import dpapi
from modules.security.vault_store import list_status, set_secret


@unittest.skipUnless(dpapi.available(), "dpapi_windows_only")
class TestNoSecretLeak(unittest.TestCase):
    def test_vault_status_only_exposes_last4(self) -> None:
        old = os.environ.get("ESTER_STATE_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["ESTER_STATE_DIR"] = tmp
                secret = "sk-live-never-leak-9988"
                res = set_secret("OPENAI_API_KEY", secret)
                self.assertTrue(res.get("ok"))

                status = list_status(["OPENAI_API_KEY"])
                text = json.dumps(status, ensure_ascii=False)
                self.assertNotIn(secret, text)
                self.assertIn(secret[-4:], text)
                self.assertNotIn(secret[:-4], text)
        finally:
            if old is None:
                os.environ.pop("ESTER_STATE_DIR", None)
            else:
                os.environ["ESTER_STATE_DIR"] = old


if __name__ == "__main__":
    unittest.main()

