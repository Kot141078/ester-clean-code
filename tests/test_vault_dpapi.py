# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import unittest

from modules.security import dpapi
from modules.security.vault_store import get_secret, list_status, set_secret, unset_secret
from modules.state.paths import resolve_state_path


@unittest.skipUnless(dpapi.available(), "dpapi_windows_only")
class TestVaultDpapi(unittest.TestCase):
    def test_roundtrip_and_plaintext_not_in_file(self) -> None:
        old = os.environ.get("ESTER_STATE_DIR")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["ESTER_STATE_DIR"] = tmp
                secret = "sk-test-abcdef123456"
                set_res = set_secret("OPENAI_API_KEY", secret)
                self.assertTrue(set_res.get("ok"))

                loaded = get_secret("OPENAI_API_KEY")
                self.assertEqual(loaded, secret)

                vault_file = resolve_state_path("vault", "secrets.json.dpapi")
                raw = vault_file.read_text(encoding="utf-8")
                self.assertNotIn(secret, raw)

                status = list_status(["OPENAI_API_KEY"])
                self.assertTrue(status.get("ok"))
                self.assertEqual(status["providers"][0]["last4"], secret[-4:])

                rm_res = unset_secret("OPENAI_API_KEY")
                self.assertTrue(rm_res.get("ok"))
                self.assertEqual(get_secret("OPENAI_API_KEY"), "")
        finally:
            if old is None:
                os.environ.pop("ESTER_STATE_DIR", None)
            else:
                os.environ["ESTER_STATE_DIR"] = old


if __name__ == "__main__":
    unittest.main()

