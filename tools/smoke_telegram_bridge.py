# -*- coding: utf-8 -*-
# tools/smoke_telegram_bridge.py — proverka «kak bot» stuchitsya v backend
# Mosty: (yavnyy) Telegram↔Backend; (skrytye) 8000↔8010, query↔message
# Zemnoy abzats: imitiruem otpravku tekstov po dvum kontraktam i dvum portam.

import os, json, sys, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = os.getenv("BACKEND_BASE") or os.getenv("ESTER_API_BASE") or "http://127.0.0.1:8010"
def post(path, payload):
    url = f"{BASE.rstrip('/')}{path}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return -1, {"ok": False, "error": str(e)}

tests = [
    ("/chat/message",        {"query": "privet ot bota", "use_rag": True}),               # kak v telegram_bot.py (seychas)
    ("/chat/message",        {"message": "privet ot bota", "mode": "lmstudio"}),          # korrektnyy dlya legacy
    ("/ester/chat/message",  {"message": "privet ot bota", "mode": "judge"}),             # korrektnyy dlya modern
]

for path, payload in tests:
    code, j = post(path, payload)
    print(f"{path:22s} -> {code:4d} :: {json.dumps(j, ensure_ascii=False)}")