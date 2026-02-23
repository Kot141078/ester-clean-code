#!/usr/bin/env python3
"""
Pechat aktivnykh nastroek "judge" bez zapuska servera.
Smotrit tolko ENV, nichego ne menyaet.
"""
import os, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
cfg = {
    "JUDGE_MODE": os.environ.get("JUDGE_MODE", "off"),
    "JUDGE_ENDPOINT": os.environ.get("JUDGE_ENDPOINT", os.environ.get("OPENAI_API_BASE","")),
    "JUDGE_MODEL": os.environ.get("JUDGE_MODEL", os.environ.get("OPENAI_MODEL","")),
    "OPENAI_API_BASE": os.environ.get("OPENAI_API_BASE",""),
    "OPENAI_API_KEY": "***" if os.environ.get("OPENAI_API_KEY") else "",
    "LMSTUDIO_URL": os.environ.get("LMSTUDIO_URL",""),
}
print(json.dumps(cfg, ensure_ascii=False, indent=2))