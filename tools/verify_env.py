import os, sys, importlib, traceback, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
print(f"Python: {sys.version.split()[0]}  exe={sys.executable}")
try:
    flask = importlib.import_module("flask")
    print("[OK] Flask importiruetsya")
except Exception:
    print("[ERR] Flask ne importiruetsya"); traceback.print_exc()
root=os.environ.get("ESTER_STATE_DIR")
if not root: print("[ERR] ESTER_STATE_DIR ne zadan")
else:
    print("[OK] ESTER_STATE_DIR=",root)
    for p in ("vstore/structured_mem/store.json","vstore/ester_memory.json"):
        f=os.path.join(root,p); print(("[OK] Est " if os.path.exists(f) else "[ERR] Net ")+f)