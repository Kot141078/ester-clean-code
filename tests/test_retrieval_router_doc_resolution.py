from __future__ import annotations

import importlib


def _reload_modules(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.store as store
    import modules.memory.doc_store as doc_store
    import modules.memory.recent_docs as recent_docs
    import modules.memory.doc_lookup as doc_lookup
    import modules.rag.retrieval_router as retrieval_router

    store = importlib.reload(store)
    doc_store = importlib.reload(doc_store)
    recent_docs = importlib.reload(recent_docs)
    doc_lookup = importlib.reload(doc_lookup)
    retrieval_router = importlib.reload(retrieval_router)

    store._MEM.clear()
    retrieval_router._maybe_log_self_evo = lambda *args, **kwargs: None
    return store, doc_store, recent_docs, doc_lookup, retrieval_router


def _ingest_disk_doc(doc_store, *, name: str, text: str, source_path: str, meta=None) -> str:
    doc_store.memory_add = lambda *args, **kwargs: {"ok": True}
    return doc_store.ingest_document(
        raw=text.encode("utf-8"),
        orig_name=name,
        full_text=text,
        chunks=[
            {"text": text[:180], "meta": {}},
            {"text": text[180:360] or text[:180], "meta": {}},
        ],
        source_path=source_path,
        meta=meta or {"source": "test"},
    )


def test_extract_filename_candidates_trims_prefixes_and_keeps_spaces(monkeypatch, tmp_path):
    _store, _doc_store, _recent_docs, doc_lookup, _rr = _reload_modules(monkeypatch, tmp_path)

    assert doc_lookup.extract_filename_candidates("что в файле Посты.txt?") == ["Посты.txt"]
    assert doc_lookup.extract_filename_candidates("что в файле LinkedIn posts.txt") == ["LinkedIn posts.txt"]


def test_retrieval_router_resolves_explicit_doc_name_from_disk_store(monkeypatch, tmp_path):
    store, doc_store, _recent_docs, _doc_lookup, retrieval_router = _reload_modules(monkeypatch, tmp_path)

    doc_id = _ingest_disk_doc(
        doc_store,
        name="Посты.txt",
        text=(
            "AGI as Advanced Global Intelligence.\n"
            "A post about public release, distributed cybernetics and protocol design.\n"
            "The file contains multiple dated posts and links."
        ),
        source_path=str(tmp_path / "telegram" / "20260316_085459_Посты.txt"),
    )

    store._MEM["wrong_summary"] = {
        "id": "wrong_summary",
        "type": "doc_summary",
        "text": "Fresh Kubit note that should not win against explicit filename resolution.",
        "meta": {"doc_id": "wrong-doc", "source": str(tmp_path / "fresh.md")},
        "ts": 1_775_000_000,
        "vec": [1.0, 0.0, 0.0],
    }

    rr = retrieval_router.retrieve("Лия, Дочка, а разве ты не увидела этот пост в файле Посты.txt?")

    assert rr["stats"]["resolved_doc"] is True
    assert rr["provenance"]
    assert rr["provenance"][0]["doc_id"] == doc_id
    assert "Посты.txt" in rr["context"]
    assert "Kubit" not in rr["context"]


def test_retrieval_router_uses_persisted_recent_doc_for_followup(monkeypatch, tmp_path):
    store, doc_store, recent_docs, _doc_lookup, retrieval_router = _reload_modules(monkeypatch, tmp_path)

    doc_id = _ingest_disk_doc(
        doc_store,
        name="Посты.txt",
        text=(
            "A note about a specific post.\n"
            "This summary should be returned on recent follow-up.\n"
            "The content is stored on disk, not in active memory."
        ),
        source_path=str(tmp_path / "telegram" / "20260316_085459_Посты.txt"),
    )
    recent_docs.remember_recent_doc(
        777,
        doc_id=doc_id,
        name="Посты.txt",
        summary="Recent summary for Посты.txt with the key post mentioned.",
        citations=["[Посты.txt | p. ?]"],
        source_path=str(tmp_path / "telegram" / "20260316_085459_Посты.txt"),
    )

    store._MEM["wrong_summary"] = {
        "id": "wrong_summary",
        "type": "doc_summary",
        "text": "Another fresh document that should not override recent follow-up.",
        "meta": {"doc_id": "wrong-doc", "source": str(tmp_path / "fresh.md")},
        "ts": 1_775_000_000,
        "vec": [1.0, 0.0, 0.0],
    }

    rr = retrieval_router.retrieve("разве ты не увидела этот пост", chat_id=777)

    assert rr["stats"]["resolved_doc"] is True
    assert rr["provenance"]
    assert rr["provenance"][0]["doc_id"] == doc_id
    assert "Посты.txt" in rr["context"]


def test_retrieval_router_followup_prefers_last_resolved_doc_binding(monkeypatch, tmp_path):
    store, doc_store, recent_docs, _doc_lookup, retrieval_router = _reload_modules(monkeypatch, tmp_path)

    target_id = _ingest_disk_doc(
        doc_store,
        name="Посты.txt",
        text=(
            "This is the document that should stay bound after explicit resolution.\n"
            "It discusses a specific post and several precise conclusions.\n"
            "The follow-up should remain attached to this file."
        ),
        source_path=str(tmp_path / "telegram" / "20260316_085459_Посты.txt"),
        meta={"source": "telegram", "chat_id": "777", "user_id": "42"},
    )
    fresher_id = _ingest_disk_doc(
        doc_store,
        name="Свежий отчет.txt",
        text=(
            "A fresher but unrelated document.\n"
            "It should not steal the follow-up after the user explicitly resolved another file."
        ),
        source_path=str(tmp_path / "telegram" / "20260317_085459_Свежий отчет.txt"),
        meta={"source": "telegram", "chat_id": "777", "user_id": "42"},
    )

    recent_docs.remember_recent_doc(
        777,
        doc_id=target_id,
        name="Посты.txt",
        summary="Target summary.",
        citations=["[Посты.txt | p. ?]"],
        source_path=str(tmp_path / "telegram" / "20260316_085459_Посты.txt"),
    )
    recent_docs.remember_recent_doc(
        777,
        doc_id=fresher_id,
        name="Свежий отчет.txt",
        summary="Fresh unrelated summary.",
        citations=["[Свежий отчет.txt | p. ?]"],
        source_path=str(tmp_path / "telegram" / "20260317_085459_Свежий отчет.txt"),
    )

    explicit = retrieval_router.retrieve("что в файле Посты.txt", chat_id=777, user_id=42)
    assert explicit["stats"]["resolved_doc"] is True
    assert explicit["provenance"][0]["doc_id"] == target_id

    followup = retrieval_router.retrieve("и это всё?", chat_id=777, user_id=42)

    assert followup["stats"]["resolved_doc"] is True
    assert followup["provenance"][0]["doc_id"] == target_id
    assert fresher_id != target_id
    assert "Посты.txt" in followup["context"]


def test_retrieval_router_resolves_explicit_filename_globally_across_chats(monkeypatch, tmp_path):
    store, doc_store, _recent_docs, _doc_lookup, retrieval_router = _reload_modules(monkeypatch, tmp_path)

    doc_id = _ingest_disk_doc(
        doc_store,
        name="Old_AGI_Notes.txt",
        text=(
            "Advanced Global Intelligence notes stored in another chat.\n"
            "This file should still be found by exact filename recall."
        ),
        source_path=str(tmp_path / "telegram" / "other_chat" / "Old_AGI_Notes.txt"),
        meta={"source": "telegram", "chat_id": "100", "user_id": "100"},
    )

    store._MEM["wrong_summary"] = {
        "id": "wrong_summary",
        "type": "doc_summary",
        "text": "Fresh local distraction that should not override explicit filename global recall.",
        "meta": {"doc_id": "wrong-doc", "source": str(tmp_path / "fresh.md")},
        "ts": 1_775_000_000,
        "vec": [1.0, 0.0, 0.0],
    }

    rr = retrieval_router.retrieve("прочитай Old_AGI_Notes.txt", chat_id=777, user_id=42)

    assert rr["stats"]["resolved_doc"] is True
    assert rr["provenance"][0]["doc_id"] == doc_id
    assert "Old_AGI_Notes.txt" in rr["context"]


def test_retrieval_router_filters_internal_signals_from_flashback(monkeypatch, tmp_path):
    store, _doc_store, _recent_docs, _doc_lookup, retrieval_router = _reload_modules(monkeypatch, tmp_path)

    retrieval_router._vector_rank = lambda query, records, topk: [dict(r) for r in records]

    store._MEM["internal_fact"] = {
        "id": "internal_fact",
        "type": "fact",
        "text": "[DISCOVERY_SCAN] found=750",
        "meta": {"source": "discovery_loader", "scope": "internal"},
        "ts": 1_775_000_001,
        "vec": [1.0, 0.0, 0.0],
    }
    store._MEM["user_fact"] = {
        "id": "user_fact",
        "type": "fact",
        "text": "Пользователь хотел проверить важный пост позже.",
        "meta": {"chat_id": "777", "user_id": "42"},
        "ts": 1_775_000_002,
        "vec": [1.0, 0.0, 0.0],
    }

    rr = retrieval_router.retrieve("важный пост", chat_id=777, user_id=42)

    assert rr["stats"]["flashback_hits"] == 1
    assert rr["stats"]["flashback_filtered"] >= 1
    assert "Пользователь хотел проверить важный пост позже." in rr["context"]
    assert "[DISCOVERY_SCAN]" not in rr["context"]


def test_doc_store_name_cache_invalidates_after_new_ingest(monkeypatch, tmp_path):
    _store, doc_store, _recent_docs, _doc_lookup, _retrieval_router = _reload_modules(monkeypatch, tmp_path)

    _ingest_disk_doc(
        doc_store,
        name="Alpha.txt",
        text="alpha document",
        source_path=str(tmp_path / "alpha.txt"),
    )
    first = doc_store.find_docs_by_name("Alpha.txt", limit=1)
    assert first and first[0]["name"] == "Alpha.txt"

    _ingest_disk_doc(
        doc_store,
        name="Beta.txt",
        text="beta document",
        source_path=str(tmp_path / "beta.txt"),
    )
    second = doc_store.find_docs_by_name("Beta.txt", limit=1)

    assert second and second[0]["name"] == "Beta.txt"
