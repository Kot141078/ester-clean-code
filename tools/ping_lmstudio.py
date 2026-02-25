# -*- coding: utf-8 -*-
import os, json, time, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = os.getenv("LMSTUDIO_BASE", "http://127.0.0.1:1234").rstrip("/")
MODEL = os.getenv("LMSTUDIO_MODEL", "gpt-4o-mini")

def json_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def json_post(url, body, timeout=60):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    print(f"[lmstudio] base={BASE}")
    try:
        t0 = time.time()
        models = json_get(f"{BASE}/v1/models", timeout=5)
        dt = time.time() - t0
        print(f"[lmstudio] /v1/models ok in {dt:.2f}s: {models.get('data')[:1]}")
    except Exception as e:
        print(f"[lmstudio] /v1/models ERROR: {e}")
        return

    body = {
        "model": MODEL,
        "messages": [{"role":"user","content":"Answer with the word PONG"}],
        "max_tokens": 16,
        "temperature": 0.0,
        "stream": False
    }
    try:
        t0 = time.time()
        out = json_post(f"{BASE}/v1/chat/completions", body, timeout=30)
        dt = time.time() - t0
        txt = out.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"[lmstudio] chat ok in {dt:.2f}s: {txt!r}")
    except Exception as e:
        print(f"[lmstudio] chat ERROR: {e}")

if __name__ == "__main__":
    main()