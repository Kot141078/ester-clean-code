from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_mm_cards_facade_compatible(monkeypatch, tmp_path):
    # Podgotovim okruzhenie
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    # Importiruem kanonnye moduli
    import cards_memory as CM  # type: ignore
    import memory_manager as MM  # type: ignore
    import structured_memory as SM  # type: ignore
    import vector_store as VS  # type: ignore

    # Patch sovmestimosti
    from modules.mm_compat import patch_memory_manager  # type: ignore

    patch_memory_manager()

    v = VS.VectorStore(collection_name="t", persist_dir=str(tmp_path), use_embeddings=False)
    s = SM.StructuredMemory(str(tmp_path / "structured_mem" / "store.json"))
    c = CM.CardsMemory(str(tmp_path / "ester_cards.json"))
    m = MM.MemoryManager(v, s, c)

    # Ubedimsya, chto svoystvo cards dostupno i metod add_card s (header, body) rabotaet
    card_id = m.cards.add_card(
        header="Zagolovok", body="Telo kartochki", tags=["ui", "test"], weight=0.7
    )
    assert isinstance(card_id, str) and len(card_id) > 0

    # I chto iskhodnyy API medium_cards ostalsya rabochim
    card_id2 = m.medium_cards.add_card(user="default", text="legacy text", tags=["legacy"])
    assert isinstance(card_id2, str) and len(card_id2) > 0