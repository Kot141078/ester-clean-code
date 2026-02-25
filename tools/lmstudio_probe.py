#!/usr/bin/env python3
"""
Proba svyazi s LM Studio / sovmestimym API.
ENV:
  LMSTUDIO_URL=http://127.0.0.1:1234/v1
Vyvodit spisok modeley (id, owned_by) i status.
"""
import os, json, urllib.request, urllib.error, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

URL = os.environ.get("LMSTUDIO_URL", "http://127.0.0.1:1234/v1").rstrip("/")
def get(url):
    req = urllib.request.Request(url, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    try:
        data = get(URL + "/models")
    except Exception as e:
        print(f"yRRsch No response from ZZF0Z/models: ZZF1ZZ")
        return 2
    models = data.get("data") or data.get("models") or []
    print(f"yuOKsh Connected: ZZF0Z models: ZZF1ZZ")
    for m in models:
        mid = m.get("id") or m.get("name") or "<?>"
        own = m.get("owned_by") or m.get("format") or ""
        print(f" - {mid}  {own}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())