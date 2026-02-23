import os
import json
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

LOG_PATH = os.path.join(Path.home(), ".ester", "vstore", "net_search_log.json")
OUT_PATH = os.path.join(os.getcwd(), "net_search_log_dump.json")

if not os.path.exists(LOG_PATH):
    print(f"[ERROR] Log file not found: {LOG_PATH}")
    exit(1)

entries = []
with open(LOG_PATH, "r", encoding="utf-8") as f:
    for line in f:
        try:
            obj = json.loads(line)
            entries.append(obj)
        except Exception as e:
            print(f"[SKIP] Corrupt line: {e}")

with open(OUT_PATH, "w", encoding="utf-8") as out:
    json.dump(entries, out, ensure_ascii=False, indent=2)

print(f"[OK] Exported {len(entries)} records → {OUT_PATH}")