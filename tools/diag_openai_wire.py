# -*- coding: utf-8 -*-
"""
Bridges (explicit): Jaynes (proveryay nablyudeniya pered vyvodami) + inzhenernaya otladka (provod/razem/endpoint) -> ne filosofstvuem, meryaem.
(hidden): Ashby (regulyator dolzhen videt signal), Cover&Thomas (esli kanal podmenen, poluchish "ekho").
Zemnoy abzats: eto kak podklyuchit manometr k vozdukhu vmesto gidrolinii — pokazaniya budut, a smysla net.
"""

import os
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def mask(s: str, keep=4):
    if not s:
        return "<empty>"
    if len(s) <= keep * 2:
        return f"{s[:1]}***{s[-1:]}"
    return f"{s[:keep]}***{s[-keep:]} (len={len(s)})"

def main():
    key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or ""
    print("OPENAI_API_KEY:", mask(key))
    print("OPENAI_BASE_URL/API_BASE:", base_url or "<default>")

    # Esli base_url sluchayno ukazyvaet na localhost — vot tebe i "ekho"
    if "127.0.0.1" in base_url or "localhost" in base_url:
        print("[WARN] OpenAI base url points to localhost. This will not hit OpenAI.")
    try:
        import openai  # noqa
        print("openai package:", getattr(openai, "__version__", "<unknown>"))
    except Exception as e:
        print("openai import failed:", e)
        sys.exit(2)

    # Probuem novyy klient
    try:
        from openai import OpenAI
        client = OpenAI()
        models = client.models.list()
        print("[OK] models.list() returned:", len(getattr(models, "data", []) or []))
        return
    except Exception as e:
        print("[FAIL] OpenAI() path:", repr(e))

    # Probuem staryy put
    try:
        import openai
        if hasattr(openai, "Model") and hasattr(openai.Model, "list"):
            models = openai.Model.list()
            data = models.get("data", [])
            print("[OK] openai.Model.list() returned:", len(data))
            return
        print("[INFO] old API not available in this openai package.")
    except Exception as e:
        print("[FAIL] openai.Model.list() path:", repr(e))

if __name__ == "__main__":
    main()