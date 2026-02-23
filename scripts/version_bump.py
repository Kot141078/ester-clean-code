# -*- coding: utf-8 -*-
import pathlib
import re
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

p = pathlib.Path("VERSION")
ver = p.read_text().strip() if p.exists() else "0.0.0"
major, minor, patch = map(int, ver.split("."))
kind = (sys.argv[1] if len(sys.argv) > 1 else "patch").lower()
if kind == "major":
    major += 1
    minor = 0
    patch = 0
elif kind == "minor":
    minor += 1
    patch = 0
else:
    patch += 1
new = f"{major}.{minor}.{patch}"
p.write_text(new)
print(new)