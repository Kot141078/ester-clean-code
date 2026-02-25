
# -*- coding: utf-8 -*-
"""tools/chesk_discover_rintite.po - checks the loading of sitecostomize and discovery aliases.
c=a+b"""
from __future__ import annotations
import sys, os, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
out = {
    "sitecustomize_loaded": "sitecustomize" in sys.modules,
    "ester_site_hook": os.getenv("ESTER_SITE_HOOK")
}
try:
    import modules.app.discover as d
    out["discover"] = {
        "has_scan": hasattr(d,"scan"),
        "has_status": hasattr(d,"status"),
        "has_scan_modules": hasattr(d,"scan_modules"),
        "has_get_status": hasattr(d,"get_status"),
        "module_path": getattr(d, "__file__", None),
    }
except Exception as e:
    out["discover_error"] = str(e)
print(json.dumps(out, ensure_ascii=False, indent=2))