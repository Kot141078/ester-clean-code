
# -*- coding: utf-8 -*-
"""
modules.lmstudio — tonkaya prosloyka nad llm.autoconfig_settings.
Mosty:
- Yavnyy: (LM Studio ↔ Nastroyki) — funktsii detect()/client() sovmestimy so starymi vyzovami.
- Skrytyy #1: (Bezopasnost) — ne ukhodit v set bez ENV.
- Skrytyy #2: (Stabilnost) — sovmestim s modules.llm.broker.

Zemnoy abzats:
Nuzhen adres LM Studio i imya modeli, chtoby lokalno otvechat bez oblaka.
# c=a+b
"""
from __future__ import annotations
from modules.llm.autoconfig_settings import detect_local_llm, LLMConfig
import urllib.request, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def detect() -> LLMConfig:
    return detect_local_llm()

def client():
    cfg = detect()
    # Prostaya obertka HTTP; realnyy klient pust daet broker
    class _C:
        endpoint = cfg.endpoint
        model = cfg.model
        timeout = cfg.timeout
        def info(self):
            return {"endpoint": self.endpoint, "model": self.model}
    return _C()