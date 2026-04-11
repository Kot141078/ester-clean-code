# dbg_rag_status.py
import os, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=ROOT / ".env", override=True)

print("== env peek ==")
for k in ("ESTER_RAG_ENABLE","ESTER_RAG_DOCS_DIR","ESTER_RAG_FORCE_PATH",
          "ESTER_VECTOR_DB","ESTER_VECTOR_DIR"):
    print(f"{k}={os.getenv(k)}")

from modules.rag import file_readers as fr
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
print("\n== fr.debug_status() ==")
print(json.dumps(fr.debug_status(), ensure_ascii=False, indent=2))
