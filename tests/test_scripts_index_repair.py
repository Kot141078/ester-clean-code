# -*- coding: utf-8 -*-
import json
import os

from scripts.rebuild_structured_index import rebuild
from scripts.repair_vectorstores import repair
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_rebuild_structured_index(tmp_path):
    p = tmp_path / "ester_memory.json"
    p.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "id": "1",
                        "text": "Privet",
                        "tags": ["a"],
                        "weight": "0.5",
                        "mtime": 0,
                    },
                    {"id": "", "text": "bez id", "tags": [], "weight": 1, "mtime": 0},
                ],
                "alias_map": {"old": "new"},
            },
            ensure_ascii=False,
        )
    )
    out = rebuild(str(p))
    assert os.path.isfile(out)
    data = json.loads(open(out, "r", encoding="utf-8").read())
    assert len(data["records"]) == 1
    assert data["alias_map"] == {"old": "new"}


def test_repair_vectorstores(tmp_path, monkeypatch):
    # podgotavlivaem VectorStore fayl
    from vector_store import VectorStore

    vs = VectorStore(collection_name="t", persist_dir=str(tmp_path), use_embeddings=False)
    # «lomaem» odnu zapis: pustoy tekst
    raw = json.loads(open(vs.path, "r", encoding="utf-8").read())
    some_id = next(iter(raw["docs"].keys()))
    raw["docs"][some_id]["text"] = ""
    open(vs.path, "w", encoding="utf-8").write(json.dumps(raw, ensure_ascii=False))
    # remontiruem
    out = repair("t", str(tmp_path))
    assert os.path.isfile(out)
    fixed = json.loads(open(out, "r", encoding="utf-8").read())
    # zapis bez teksta udalena
    assert some_id not in fixed["docs"]
