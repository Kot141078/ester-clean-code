# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
import tempfile
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# ------------------------------- utils -------------------------------

def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v if isinstance(v, str) else default


def _expand(p: str) -> str:
    """Raskryvaem ~ i peremennye okruzheniya, privodim k str."""
    p = p or ""
    return os.path.expanduser(os.path.expandvars(p))


def _fix_common_mispath(raw: str) -> str:
    """
    Avto-pravka chastoy oshibki v .env:
      '%USERPROFILE%.ester'  -> '%USERPROFILE%\\.ester'
      'C:\\Users\\<user>.ester' -> 'C:\\Users\\<user>\\.ester'
    """
    if not raw:
        return raw
    s = raw.replace("/", "\\")
    # vstavim obratnyy slesh pered ".ester", esli ego net
    if s.lower().endswith(".ester") and "\\.ester" not in s.lower():
        # esli stroka vyglyadit kak '...\\Users\\<name>.ester' — chinim
        parts = s.split("\\")
        if len(parts) >= 3 and parts[-1].lower().endswith(".ester"):
            parts[-1] = "." + parts[-1]  # na sluchay redkikh variantov
        s = s.replace(".ester", "\\.ester")
    return s


def _try_mkdir(path_str: str) -> Optional[Path]:
    """Probuem sozdat katalog; pri otkaze vozvraschaem None (bez isklyucheniy)."""
    try:
        p = Path(path_str)
        p.mkdir(parents=True, exist_ok=True)
        return p
    except PermissionError:
        return None
    except OSError:
        return None


def _vectors_root() -> Path:
    """
    Vybiraem rabochuyu papku dlya vektornogo khranilischa po prioritetu:
      1) ESTER_VECTOR_DIR
      2) ESTER_DATA_ROOT\\vstore\\vectors
      3) %USERPROFILE%\\.ester\\vstore\\vectors
      4) %TEMP%\\ester\\vstore\\vectors  (na krayniy sluchay)
    """
    candidates: List[str] = []

    ev = _expand(_fix_common_mispath(_env("ESTER_VECTOR_DIR")))
    if ev:
        candidates.append(ev)

    dr = _expand(_fix_common_mispath(_env("ESTER_DATA_ROOT")))
    if dr:
        candidates.append(os.path.join(dr, "vstore", "vectors"))

    # defolt v profile polzovatelya
    candidates.append(os.path.join(_expand("~"), ".ester", "vstore", "vectors"))

    # obkhodim kandidatov — sozdaem pervyy dostupnyy
    for c in candidates:
        if not c:
            continue
        p = _try_mkdir(c)
        if p:
            return p

    # sovsem uzh bezopasnyy otkat — TEMP (vsegda dolzhen suschestvovat)
    temp_fallback = Path(tempfile.gettempdir()) / "ester" / "vstore" / "vectors"
    temp_fallback.mkdir(parents=True, exist_ok=True)
    return temp_fallback


def _persist_fallback(docs: List[Dict[str, Any]], tag: str) -> Dict[str, Any]:
    """
    Faylovyy follbek: pishem JSONL, chtoby nichego ne poteryat dazhe bez vektorki.
    Zaschischen ot PermissionError — pri problemakh s pravami avtomaticheski
    otkatyvaetsya v %TEMP%.
    """
    root = _vectors_root()
    out = root / "rag_corpus.jsonl"
    ing = 0
    with out.open("a", encoding="utf-8") as f:
        for d in docs:
            rec = {
                "id": d.get("id"),
                "text": d.get("text", ""),
                "meta": {**(d.get("meta") or {}), "tag": tag},
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            ing += 1
    return {"ok": True, "ingested": ing, "path": str(out), "via": "fallback_jsonl"}


def _norm_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizuem vkhod: garantiruem id/text/meta."""
    norm: List[Dict[str, Any]] = []
    for it in items:
        it = it or {}
        text = it.get("text", "") or ""
        meta = (it.get("meta") or {}).copy()
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        _id = meta.get("id") or it.get("id") or h
        norm.append({"id": _id, "text": text, "meta": meta})
    return norm


# ------------------------------- hub api -------------------------------

def ingest_texts(items: List[Dict[str, Any]], tag: str = "local_docs") -> Dict[str, Any]:
    """
    Unifitsirovannyy vkhod dlya indeksatsii RAG-dokov.
    Poryadok popytok:
      1) modules.rag.rag_sink / sink / hub_impl — esli suschestvuyut
      2) modules.memory.vector_store_safe_adapter — universalnyy variant
      3) Faylovyy follbek (~/.ester/vstore/vectors/rag_corpus.jsonl ili %TEMP%)
    """
    docs = _norm_items(items)

    # 1) rag_sink / sink / hub_impl
    for mod_name in ("modules.rag.rag_sink", "modules.rag.sink", "modules.rag.hub_impl"):
        try:
            mod = __import__(mod_name, fromlist=["*"])
        except Exception:
            mod = None
        if not mod:
            continue

        for fn_name, argv in (
            ("ingest_texts", (docs, tag)),
            ("ingest", (docs, tag)),
            ("add_documents", (docs, tag)),
            ("add_texts", ([d["text"] for d in docs], [d["meta"] for d in docs], tag)),
            ("add", (docs, tag)),
            ("put", (docs, tag)),
            ("index_texts", ([d["text"] for d in docs], tag)),
            ("index", (docs, tag)),
        ):
            try:
                fn = getattr(mod, fn_name, None)
                if not callable(fn):
                    continue
                try:
                    res = fn(*argv)
                except TypeError:
                    # variant s kwargs
                    res = fn(docs, tag=tag)

                ingested = None
                if isinstance(res, dict) and "ingested" in res:
                    ingested = int(res.get("ingested") or 0)
                elif isinstance(res, (list, tuple, set)):
                    ingested = len(res)
                if ingested is None:
                    ingested = len(docs)
                return {"ok": True, "ingested": ingested, "via": f"{mod_name}.{fn_name}"}
            except Exception:
                # probuem sleduyuschiy metod/modul
                continue

    # 2) vector_store_safe_adapter
    try:
        vmod = __import__("modules.memory.vector_store_safe_adapter", fromlist=["*"])
        for fn_name in ("upsert_texts", "add_texts", "put_texts", "upsert", "add", "put"):
            fn = getattr(vmod, fn_name, None)
            if not callable(fn):
                continue
            try:
                # signatura (texts, metas, tag=?)
                res = fn([d["text"] for d in docs], [d["meta"] for d in docs], tag=tag)
            except TypeError:
                # fallback na (docs, tag=?)
                res = fn(docs, tag=tag)

            ing = len(docs)
            if isinstance(res, dict) and "ingested" in res:
                ing = int(res.get("ingested") or ing)
            return {"ok": True, "ingested": ing, "via": f"vector_store_safe_adapter.{fn_name}"}
    except Exception:
        pass

    # 3) faylovyy follbek — vnutri uzhe ustoychivaya rabota s pravami
    return _persist_fallback(docs, tag)


# Sovmestimye aliasy — na sluchay vyzovov iz raznykh mest proekta
def ingest(items: List[Dict[str, Any]], tag: str = "local_docs") -> Dict[str, Any]:
    return ingest_texts(items, tag=tag)


def add(items: List[Dict[str, Any]], tag: str = "local_docs") -> Dict[str, Any]:
    return ingest_texts(items, tag=tag)


def put(items: List[Dict[str, Any]], tag: str = "local_docs") -> Dict[str, Any]:
    return ingest_texts(items, tag=tag)
