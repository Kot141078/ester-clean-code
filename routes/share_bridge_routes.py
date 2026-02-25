# -*- coding: utf-8 -*-
"""routes/share_bridge_routes.py - drop-in Bridge-routy sovmestimye s share_bridge.py protocol.
Naznachenie: prinimat web-vydeleniya/stranitsy i pisat ikh na disk (dlya posleduyuschego ingest) i, optsionalno,
srazu v pamyat (StructuredMemory + Cards) dlya mgnovimoy dostupnosti v RAG/fide/UI.

Endpoint:
  POST /share/capture
    — odinochnyy obekt: {url,title,html?,text?,selection?,tags?,note?}
    — paket: {"items":[{...},{...}]}
Answer (supermnozhestvo prezhnego):
  {"ok":true,"count":N,
   "saved":[
     {
       "id":"<record-id|None>",
       "title":"...",
       "relpaths":["file.ext","file.meta.json"],   # otnositelnye puti vnutri inbox
       "meta": "<abs path to meta.json>",
       "html": "<abs path to html>" |  # esli sokhranen HTML
       "txt":  "<abs path to txt>"     # esli sokhranen tekst
     }, ...
   ]}

ENV:
  PERSIST_DIR - koren dannykh (kak v drugikh modulyakh)
  ESTER_INGEST_INBOX — direktoriya dlya syrya (by umolchaniyu PERSIST_DIR/ingest/bridge_inbox)
  SHARE_MAX_HTML_MB - limit size HTML v megabaytakh (by default 8)
  SHARE_WRITE_MEMORY - 1/0: pisat v StructuredMemory/kartochki (po umolchaniyu 1)
Sovmestimost:
  - Polya "html"/"txt" i "meta" sokhraneny dlya obratnoy sovmestimosti s v1-testami.
  - Put i signatury ne izmeneny. Mozhno rabotat kak "chistyy dropper", esli SHARE_WRITE_MEMORY=0."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from flask import jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --------------------------- utils & env ---------------------------


def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    return base


def _inbox_dir() -> str:
    root = _persist_dir()
    default = os.path.join(root, "ingest", "bridge_inbox")
    path = os.getenv("ESTER_INGEST_INBOX", default)
    os.makedirs(path, exist_ok=True)
    return path


def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\s-]+", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:80].strip("-") or "untitled"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _host_tag(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url).netloc or ""
        if host:
            return f"src:{host}"
    except Exception:
        return None
    return None


def _normalize_tags(tags) -> List[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",") if t.strip()]
    if isinstance(tags, list):
        return [str(t).strip() for t in tags if str(t).strip()]
    return []


def _normalize_item(it: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "url": str(it.get("url") or "").strip(),
        "title": str(it.get("title") or "untitled").strip(),
        "html": str(it.get("html") or ""),
        "text": str(it.get("text") or ""),
        "selection": str(it.get("selection") or ""),
        "tags": _normalize_tags(it.get("tags")),
        "note": it.get("note"),
    }


# --------------------------- memory wiring ---------------------------


def _build_mm():
    # Canonical memory assembly - without changing imports/paths
    from cards_memory import CardsMemory  # type: ignore
    from memory_manager import MemoryManager  # type: ignore
    from structured_memory import StructuredMemory  # type: ignore
    from vector_store import VectorStore  # type: ignore

    persist_dir = _persist_dir()
    vstore = VectorStore(
        collection_name=os.getenv("COLLECTION_NAME", "ester_store"),
        persist_dir=persist_dir,
        use_embeddings=bool(int(os.getenv("USE_EMBEDDINGS", "0"))),
        embeddings_api_base=os.getenv("EMBEDDINGS_API_BASE", ""),
        embeddings_model=os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        embeddings_api_key=os.getenv("EMBEDDINGS_API_KEY", ""),
        use_local=bool(int(os.getenv("EMBEDDINGS_USE_LOCAL", "1"))),
    )
    structured = StructuredMemory(os.path.join(persist_dir, "structured_mem", "store.json"))  # type: ignore
    cards = CardsMemory(os.path.join(persist_dir, "ester_cards.json"))  # type: ignore
    return MemoryManager(vstore, structured, cards)  # type: ignore


def _mm(app):
    if getattr(app, "memory_manager", None) is not None:
        return app.memory_manager  # type: ignore[attr-defined]
    mm = _build_mm()
    setattr(app, "memory_manager", mm)
    return mm


# --------------------------- save logic ---------------------------


def _save_one(
    app, item: Dict[str, Any], max_html_mb: float, write_memory: bool, inbox: str
) -> Dict[str, Any]:
    url = item["url"]
    title = item["title"] or (url.split("://", 1)[-1] if url else "Vez nazvaniya")
    html = item["html"]
    text = item["text"] or item["selection"] or ""
    tags = item["tags"]
    note = item["note"]

    # Limit HTML by size (in bytes)
    if html:
        html_bytes = html.encode("utf-8")
        max_bytes = int(max_html_mb * 1024 * 1024)
        if len(html_bytes) > max_bytes:
            html = html_bytes[: max(0, max_bytes - 1024)].decode("utf-8", errors="ignore")

    ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = f"{ts}-{_slug(title)}"
    saved_rel: List[str] = []

    abs_html = None
    abs_txt = None
    abs_meta = None

    # HTML-kontent
    if html:
        html_bytes = html.encode("utf-8")
        sha = _sha256(html_bytes)
        meta = {
            "url": url,
            "title": title,
            "sha256": sha,
            "type": "html",
            "created_utc": ts,
            "note": note,
            "tags": tags,
        }
        hp = os.path.join(inbox, base + ".html")
        mp = os.path.join(inbox, base + ".meta.json")
        with open(hp, "w", encoding="utf-8") as f:
            f.write(html)
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        saved_rel += [os.path.relpath(hp, inbox), os.path.relpath(mp, inbox)]
        abs_html, abs_meta = hp, mp

    # TEXT content (if there is no ntml)
    if text and not html:
        tb = text.encode("utf-8")
        sha = _sha256(tb)
        meta = {
            "url": url,
            "title": title,
            "sha256": sha,
            "type": "text",
            "created_utc": ts,
            "note": note,
            "tags": tags,
        }
        tp = os.path.join(inbox, base + ".txt")
        mp = os.path.join(inbox, base + ".meta.json")
        with open(tp, "w", encoding="utf-8") as f:
            f.write(text)
        with open(mp, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        saved_rel += [os.path.relpath(tp, inbox), os.path.relpath(mp, inbox)]
        abs_txt, abs_meta = tp, mp

    # Write to memory (softly, if enabled)
    rec_id = None
    if write_memory:
        try:
            mm = _mm(app)
            tagset = ["share", "web"]
            htag = _host_tag(url)
            if htag:
                tagset.append(htag)
            for t in tags:
                if t:
                    tagset.append(t[:32])
            payload_text = (text or "").strip()
            if not payload_text:
                payload_text = (html or "")[:1000]
            rec_id = mm.structured.add_record(text=payload_text, tags=tagset, weight=0.55)  # type: ignore[attr-defined]
            # card - through a compatible facade (see mm_company.patch_memory_manager)
            try:
                mm.cards.add_card(header=title, body=payload_text[:600], tags=["share"] + tags)  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            rec_id = None

    # We return Re old fields (for B1 tests), Re new ones
    out: Dict[str, Any] = {
        "id": rec_id,
        "title": title,
        "relpaths": saved_rel,
    }
    if abs_meta:
        out["meta"] = abs_meta
    if abs_html:
        out["html"] = abs_html
    if abs_txt:
        out["txt"] = abs_txt
    return out


# --------------------------- route ---------------------------


def register_share_bridge_routes(app, url_prefix: str = "/share"):
    @app.post(url_prefix + "/capture")
    @jwt_required(
        optional=True
    )  # We allow a guest for quick notes
    def share_capture():
        data = request.get_json(silent=True) or {}
        inbox = _inbox_dir()
        try:
            max_html_mb = float(os.getenv("SHARE_MAX_HTML_MB", "8"))
        except Exception:
            max_html_mb = 8.0
        write_memory = os.getenv("SHARE_WRITE_MEMORY", "1") == "1"

        saved: List[Dict[str, Any]] = []

        # Paketnyy rezhim
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            for it in data["items"]:
                try:
                    item = _normalize_item(dict(it))
                    saved.append(_save_one(app, item, max_html_mb, write_memory, inbox))
                except Exception:
                    continue
            return jsonify({"ok": True, "count": len(saved), "saved": saved})

        # Odinochnyy obekt
        try:
            item = _normalize_item(data)
            saved.append(_save_one(app, item, max_html_mb, write_memory, inbox))
        except Exception:
            return jsonify({"ok": False, "error": "bad payload"}), 400

        return jsonify({"ok": True, "count": len(saved), "saved": saved})


def _save_one(obj: Dict[str, Any]) -> Dict[str, str]:
    url = (obj.get("url") or "").strip()
    title = (obj.get("title") or "").strip() or (
        url.split("://", 1)[-1] if url else "Vez nazvaniya"
    )
    html = obj.get("html")
    text = obj.get("text")
    selection = obj.get("selection")
    note = obj.get("note")
    tags = _normalize_tags(obj.get("tags"))

    ts = time.time()
    base = f"{int(ts)}-{_slug(title)}-{_hash_key((url or '') + (title or ''))}"
    inbox = _inbox()

    meta: Dict[str, Any] = {
        "ts": ts,
        "url": url,
        "title": title,
        "tags": tags,
        "note": note,
        "selection": selection,
        "source": "share_bridge",
        "size": {
            "html": len(html or ""),
            "text": len(text or ""),
        },
    }

    # deciding what to save as main content
    if html and isinstance(html, str) and html.strip():
        html_path = os.path.join(inbox, base + ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        meta_path = os.path.join(inbox, base + ".meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return {"html": html_path, "meta": meta_path}
    else:
        # pishem tekst/selection v .txt
        body = (text or "") + ("\n\n[selection]\n" + selection if selection else "")
        txt_path = os.path.join(inbox, base + ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(body.strip())
        meta_path = os.path.join(inbox, base + ".meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return {"txt": txt_path, "meta": meta_path}


def register_share_bridge_routes(app, url_prefix: str = "/share"):
    @app.post(url_prefix + "/capture")
    @jwt_required(optional=True)
    def share_capture():
        data = request.get_json(silent=True) or {}
        saved: List[Dict[str, str]] = []

        # rezhim: paket
        if isinstance(data.get("items"), list):
            for it in data["items"]:
                try:
                    saved.append(_save_one(dict(it)))
                except Exception:
                    continue
            return jsonify({"ok": True, "saved": saved, "count": len(saved)})

        # mode: single object
        # allows fields to be passed directly to the root
        try:
            saved.append(_save_one(data))
        except Exception as e:
            return jsonify({"ok": False, "error": "bad payload"}), 400

# return jsonify({"ok": True, "saved": saved, "count": len(saved)})


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
def register(app):
    # calls an existing register_share_bridge_rutes(app) (url_prefix is ​​taken by default inside the function)
    return register_share_bridge_routes(app)

# === /AUTOSHIM ===