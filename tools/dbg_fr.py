# D:\ester-project\tools\dbg_fr.py
import os, sys, json
from pathlib import Path

# 1) so that project modules are imported
sys.path.insert(0, r"D:\ester-project")

# 2) pick up .env of this particular project
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=r"D:\ester-project\.env", override=True)
except Exception as e:
    print(f"[warn] python-dotenv not loaded: {e}")

# 3) status RAG putey
from modules.rag import file_readers as fr
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
print(json.dumps(fr.debug_status(), ensure_ascii=False, indent=2))