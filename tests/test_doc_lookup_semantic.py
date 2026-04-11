from __future__ import annotations

import importlib


def _reload_modules(monkeypatch, tmp_path):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    import modules.memory.doc_store as doc_store
    import modules.memory.recent_docs as recent_docs
    import modules.memory.doc_lookup as doc_lookup

    doc_store = importlib.reload(doc_store)
    recent_docs = importlib.reload(recent_docs)
    doc_lookup = importlib.reload(doc_lookup)
    doc_store.memory_add = lambda *args, **kwargs: {"ok": True}
    return doc_store, recent_docs, doc_lookup


def _ingest_disk_doc(doc_store, *, name: str, text: str, source_path: str, meta=None) -> str:
    return doc_store.ingest_document(
        raw=text.encode("utf-8"),
        orig_name=name,
        full_text=text,
        chunks=[
            {"text": text[:220], "meta": {}},
            {"text": text[220:440] or text[:220], "meta": {}},
        ],
        source_path=source_path,
        meta=meta or {"source": "test"},
    )


def test_doc_lookup_prefers_same_chat_exact_before_global(monkeypatch, tmp_path):
    doc_store, _recent_docs, doc_lookup = _reload_modules(monkeypatch, tmp_path)

    same_chat_id = _ingest_disk_doc(
        doc_store,
        name="SharedName.txt",
        text="Same-chat document that should win even if another chat has a fresher copy.",
        source_path=str(tmp_path / "chat777" / "SharedName.txt"),
        meta={"source": "telegram", "chat_id": "777", "user_id": "42"},
    )
    other_chat_id = _ingest_disk_doc(
        doc_store,
        name="SharedName.txt",
        text="Other-chat document with the same filename but fresher ingest time.",
        source_path=str(tmp_path / "chat999" / "SharedName.txt"),
        meta={"source": "telegram", "chat_id": "999", "user_id": "99"},
    )

    resolved = doc_lookup.resolve_doc_for_query(
        "что в файле SharedName.txt",
        chat_id=777,
        user_id=42,
    )

    assert resolved is not None
    assert resolved["doc_id"] == same_chat_id
    assert resolved["_doc_resolve_reason"] == "explicit_filename"
    assert same_chat_id != other_chat_id


def test_doc_lookup_semantic_global_recall_adds_uncertainty(monkeypatch, tmp_path):
    doc_store, _recent_docs, doc_lookup = _reload_modules(monkeypatch, tmp_path)

    main_id = _ingest_disk_doc(
        doc_store,
        name="AGI_memory_recall_notes.md",
        text=(
            "Advanced Global Intelligence protocol for memory recall across chats.\n"
            "This document explains semantic global recall, passport store lookup, and bounded follow-up handling.\n"
            "Across chats, the document should still be found when the user remembers the topic but not the filename."
        ),
        source_path=str(tmp_path / "chat100" / "AGI_memory_recall_notes.md"),
        meta={"source": "telegram", "chat_id": "100", "user_id": "100"},
    )
    _alt_id = _ingest_disk_doc(
        doc_store,
        name="AGI_memory_architecture_notes.md",
        text=(
            "Advanced Global Intelligence protocol for memory recall and retrieval architecture.\n"
            "This nearby document also discusses semantic global recall, passport store lookup, and bounded follow-up handling.\n"
            "It is similar enough that the resolver should be honest about uncertainty."
        ),
        source_path=str(tmp_path / "chat101" / "AGI_memory_architecture_notes.md"),
        meta={"source": "telegram", "chat_id": "101", "user_id": "101"},
    )

    resolved = doc_lookup.resolve_doc_for_query(
        "найди документ про AGI protocol memory recall across chats",
        chat_id=777,
        user_id=42,
    )

    assert resolved is not None
    assert resolved["doc_id"] == main_id
    assert resolved["_doc_resolve_reason"] == "semantic_global"
    assert resolved.get("_doc_recall_uncertainty")

    payload = doc_lookup.build_doc_context(resolved, "найди документ про AGI protocol memory recall across chats")
    assert "[DOC_RECALL_UNCERTAINTY]" in payload["context"]
    assert "AGI_memory_architecture_notes.md" in payload["context"]
