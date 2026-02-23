# -*- coding: utf-8 -*-
"""
scripts/smoke_rag_file_readers.py

Lokalnyy smoke-test:
- sozdaet vremennuyu papku s test-faylami,
- podstavlyaet ee v RAG_DOCS_PATH,
- proveryaet list_docs() i ingest_all().

Zapusk:
    python scripts/smoke_rag_file_readers.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# Podklyuchaem proektnyy koren
ROOT = Path(__file__).resolve().parent.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.rag import file_readers  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TEST_DIR = ROOT / "_rag_test_docs"


def main() -> None:
    # Gotovim testovuyu direktoriyu
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir(parents=True, exist_ok=True)

    (TEST_DIR / "a.txt").write_text("hello from rag", encoding="utf-8")
    (TEST_DIR / "b.md").write_text("# title\ncontent", encoding="utf-8")

    os.environ["RAG_ENABLE"] = "1"
    os.environ["RAG_DOCS_PATH"] = str(TEST_DIR)

    items = file_readers.list_docs()
    assert len(items) == 2, f"expected 2 docs, got {len(items)}"

    res = file_readers.ingest_all(tag="test")
    assert res.get("ok") is True, res
    assert res.get("total", 0) >= 2

    print("[OK] file_readers.list_docs() works.")
    print("[OK] file_readers.ingest_all() returns:", res)
    print("[SMOKE] rag_file_readers ready.")


if __name__ == "__main__":
    main()