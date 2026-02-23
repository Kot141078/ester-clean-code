# -*- coding: utf-8 -*-
"""
tools/smoke.py — CLI-obertka poverkh /tools/smoke/run: polezno dlya lokalnoy proverki.

Zemnoy abzats:
Zapusk iz konsoli dlya bystrogo pinga — udobno v CI ili pered vykatom.

# c=a+b
"""
import json, urllib.request, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main():
    fast = ("--fast" in sys.argv)
    data = json.dumps({"fast": fast}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:8000/tools/smoke/run", data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=21600) as r:
        rep = json.loads(r.read().decode("utf-8"))
        ok = rep.get("ok", False)
        print("[SMOKE]", "OK" if ok else "FAIL", f"({rep.get('ok_n',0)}/{rep.get('total',0)})")
        for it in rep.get("results", []):
            flag = "✓" if it.get("ok") else "✗"
            print(flag, it.get("name",""), it.get("method",""), it.get("path",""), f"{it.get('dur_s',0)}s")
        sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
# c=a+b




