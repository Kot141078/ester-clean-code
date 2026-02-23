# -*- coding: utf-8 -*-
from vector_store import VectorStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_vector_store_add_and_search(tmp_path):
    vs = VectorStore(collection_name="test", persist_dir=str(tmp_path), use_embeddings=False)
    ids = vs.add_texts(
        ["kot lyubit moloko", "sobaka lyubit kost"], meta={"src": "t"}
    )
    assert len(ids) == 2
    hits = vs.search("kot", k=1)
# assert hits and "kot" in hits[0]["text"]