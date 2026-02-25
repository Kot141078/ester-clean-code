#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_mm_access.py - oflayn-scanner na “obkhod get_mm”.

Mosty:
- Yavnyy: (Linter ↔ Kodovaya baza) ischet podozritelnye konstruktsii i flaguet cherez REST.
- Skrytyy #1: (MM Guard ↔ Audit) pishet result v /mm/audit/flag.
- Skrytyy #2: (CI ↔ Kachestvo) mozhet ispolzovatsya v lokalnom pre-commit.

Zemnoy abzats:
Kak fonarik v arkhive: bystro podsvetit mesta, where mogli napryamuyu lezt k pamyati, minuya fabriku.

# c=a+b"""
import os, re, json, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.getcwd()
PATTERNS = [
    re.compile(r"\bMemoryManager\s*\("),
    re.compile(r"\bVectorStore\s*\("),
    re.compile(r"from\s+services\.mm_access\s+import\s+(?!get_mm)\w+"),
]

def flag(path, reason):
    try:
        data=json.dumps({"path": path, "reason": reason}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000/mm/audit/flag", data=data, headers={"Content-Type":"application/json"})
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass

def scan():
    findings=[]
    for base in ("modules","routes","services"):
        bpath=os.path.join(ROOT, base)
        if not os.path.isdir(bpath): continue
        for dp,_,files in os.walk(bpath):
            for n in files:
                if not n.endswith(".py"): continue
                p=os.path.join(dp,n)
                try:
                    s=open(p,"r",encoding="utf-8").read()
                except Exception:
                    continue
                for rx in PATTERNS:
                    if rx.search(s):
                        findings.append({"path": p, "reason": f"suspect:{rx.pattern}"})
                        flag(p, f"suspect:{rx.pattern}")
    print(json.dumps({"ok": True, "findings": findings}, ensure_ascii=False, indent=2))

if __name__=="__main__":
    scan()
# c=a+b