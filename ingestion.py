# -*- coding: utf-8 -*-
from __future__ import annotations

"""ingestion.py - /ingest/*: upload → parse → chunk → index (vstore) → (optional) summarize.

Provaydery (po tvoemu.env):
- local/lmstudio: LMSTUDIO_BASE_URL + LMSTUDIO_MODEL + LMSTUDIO_TIMEOUT
- openai (optsionalno): OPENAI_API_BASE + OPENAI_API_KEY + OPENAI_MODEL
(nikakikh groq/xai)

Yavnyy most (L4):
- summarizatsiya = raskhod resursa (vremya/energiya/tokeny) → vyklyuchena po umolchaniyu (INGEST_SUMMARIZE=1 vklyuchaet).

Skrytye mosty:
- Bayes/Jaynes: “net dannykh” ≠ “net istiny” → fallback na lokalnye now_iso/sha256, esli file_readers ne daet.
- Talmud/Avot (ideya distsipliny): zapreschaem URL ingest po umolchaniyu, vklyuchaetsya flagom.

Zemnoy abzats:
Inzhest - eto kak priemka syrya na proizvodstve: snachala kontrol (razmer/tip), potom narezka,
potom warehouse (indexes). I tolko esli nado - “shef-zametki” (summary), inache gorelka ne vyklyuchitsya."""

import hashlib
import json
import os
import queue
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from flask import Blueprint, jsonify, request, current_app

from chunking import chunk_document  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# -------------------------
# Folbeki: now_iso / sha256_bytes / detect_and_read
# -------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b or b"").hexdigest()

def _fallback_detect_and_read(filename: str, raw: bytes) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    text = ""
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1251", "latin-1"):
        try:
            text = (raw or b"").decode(enc)
            break
        except Exception:
            continue
    if not text:
        text = (raw or b"").decode("utf-8", errors="replace")

    ext = os.path.splitext(filename or "")[1].lower()
    mime = "text/plain"
    if ext in (".json", ".jsonl"):
        mime = "application/json"
    elif ext in (".yaml", ".yml"):
        mime = "text/yaml"
    elif ext in (".py",):
        mime = "text/x-python"
    elif ext in (".md",):
        mime = "text/markdown"

    head = {"title": filename or "document", "mime": mime, "ext": ext, "lang": "ru"}
    sections = [{"kind": "text", "title": head["title"], "index": 0, "text": text}]
    return sections, text, head

try:
    import file_readers as _fr  # type: ignore
    if hasattr(_fr, "now_iso"):
        now_iso = _fr.now_iso  # type: ignore
    if hasattr(_fr, "sha256_bytes"):
        sha256_bytes = _fr.sha256_bytes  # type: ignore
    if hasattr(_fr, "detect_and_read"):
        detect_and_read = _fr.detect_and_read  # type: ignore
    else:
        detect_and_read = _fallback_detect_and_read  # type: ignore
except Exception:
    detect_and_read = _fallback_detect_and_read  # type: ignore


# -------------------------
# Puti/konfig (po .env)
# -------------------------

def _env_path(*keys: str, default: str = "") -> str:
    for k in keys:
        v = os.environ.get(k, "")
        if v:
            return v
    return default

DATA_ROOT = _env_path("ESTER_DATA_ROOT", "PERSIST_DIR", default=os.path.join(os.getcwd(), "data"))
LOG_DIR = _env_path("ESTER_LOG_DIR", default=os.path.join(DATA_ROOT, "logs"))
LIB_DIR = os.path.join(DATA_ROOT, "library")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(LIB_DIR, exist_ok=True)

INGEST_SUMMARIZE = str(os.getenv("INGEST_SUMMARIZE", "0")).lower() in ("1", "true", "yes")

# URL ingest: podderzhivaem tvoi flagi
INGEST_ALLOW_URLS = (
    str(os.getenv("INGEST_ALLOW_URLS", "0")).lower() in ("1", "true", "yes")
    or str(os.getenv("ESTER_NET_INGEST_ALLOW", "0")).strip('"').lower() in ("1", "true", "yes")
)
INGEST_MAX_BYTES = int(os.getenv("INGEST_MAX_BYTES", str(50 * 1024 * 1024)))  # 50MB

# Telegram: you have ADMIN_TG_ID, but TELEGRAM_CHAT_ID may not exist
TG_ENABLED = str(os.getenv("ESTER_TELEGRAM_ENABLED", "0")).lower() in ("1", "true", "yes")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("ADMIN_TG_ID") or ""
TG_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""


# -------------------------
# LLM provider (LMStudio + optional OpenAI)
# -------------------------

def _join_url(base: str, suffix: str) -> str:
    base = (base or "").rstrip("/")
    suffix = suffix.lstrip("/")
    return f"{base}/{suffix}"

def _default_provider() -> str:
    # CLOSED_BOX_PROVIDERS=local,peer → berem pervoe
    cb = (os.getenv("CLOSED_BOX_PROVIDERS") or "").strip()
    if cb:
        first = cb.split(",")[0].strip().lower()
        if first:
            return first
    # inache PROVIDER_DEFAULT (u tebya judge) → prizemlyaem k local
    p = (os.getenv("PROVIDER_DEFAULT") or "local").strip().lower()
    if p in ("judge", "auto"):
        return "local"
    return p

LLM_PROVIDER = (os.getenv("INGEST_PROVIDER") or _default_provider()).strip().lower()

LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "local-model")
LMSTUDIO_TIMEOUT = int(os.getenv("LMSTUDIO_TIMEOUT", "600"))

OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", os.getenv("LLM_TIMEOUT", "600")))


def _trace_write(rec: Dict[str, Any]) -> None:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(LOG_DIR, f"{day}.jsonl")
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


class LLMClient:
    """Simple OpenAI-compatible client.
    provider:
      - local/lmstudio → LMSTUDIO_BASE_URL
      - openai → OPENAI_API_BASE"""

    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or LLM_PROVIDER or "local").lower()

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 1024) -> str:
        t0 = time.perf_counter()
        model_name = ""
        url = ""
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        payload: Dict[str, Any] = {}

        try:
            if self.provider in ("openai",) and OPENAI_API_KEY:
                url = _join_url(OPENAI_API_BASE, "chat/completions")
                headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
                model_name = OPENAI_MODEL
                timeout = OPENAI_TIMEOUT
            else:
                # local / lmstudio
                url = _join_url(LMSTUDIO_BASE_URL, "chat/completions")
                model_name = LMSTUDIO_MODEL
                timeout = LMSTUDIO_TIMEOUT

            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": float(temperature),
                "max_tokens": int(max_tokens),
            }

            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]

        finally:
            dt_ms = int((time.perf_counter() - t0) * 1000)
            prompt_text = "\n".join([(m.get("content") or "") for m in (messages or [])])
            _trace_write(
                {
                    "ts": now_iso(),
                    "provider": self.provider,
                    "model": model_name,
                    "latency_ms": dt_ms,
                    "tokens_prompt_est": max(1, int(len(prompt_text) / 4)) if prompt_text else 0,
                    "note": "LLMClient.chat",
                }
            )

LLM = LLMClient()


# -------------------------
# Index + jobs
# -------------------------

class JobState:
    def __init__(self, job_id: str, items: List[Dict[str, Any]]):
        self.job_id = job_id
        self.created_at = now_iso()
        self.status = "queued"
        self.progress = 0.0
        self.error: Optional[str] = None
        self.items = items
        self.results: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "created_at": self.created_at,
            "status": self.status,
            "progress": round(self.progress, 2),
            "error": self.error,
            "items": self.items,
            "results": self.results,
        }


class IngestionIndex:
    PATH = os.path.join(LIB_DIR, "_index.json")

    def __init__(self):
        self._lock = threading.RLock()
        self.data: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        with self._lock:
            if os.path.exists(self.PATH):
                try:
                    with open(self.PATH, "r", encoding="utf-8") as f:
                        self.data = json.load(f) or []
                except Exception:
                    self.data = []
            else:
                self.data = []

    def _save(self) -> None:
        with self._lock:
            with open(self.PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add(self, meta: Dict[str, Any]) -> None:
        with self._lock:
            doc_id = meta.get("doc_id")
            self.data = [x for x in self.data if x.get("doc_id") != doc_id]
            self.data.insert(0, meta)
            self.data = self.data[:1000]
            self._save()

    def delete(self, doc_id: str) -> None:
        with self._lock:
            self.data = [x for x in self.data if x.get("doc_id") != doc_id]
            self._save()

    def list(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.data[:limit])

INDEX = IngestionIndex()


def notify_done(title: str, doc_id: str) -> None:
    if not (TG_ENABLED and TG_TOKEN and TG_CHAT_ID):
        return
    msg = f"📚 Prochitala i osmyslila: {title}\n(doc_id={doc_id})"
    try:
        api = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(api, json={"chat_id": TG_CHAT_ID, "text": msg}, timeout=10)
    except Exception:
        pass


def _doc_dir(doc_id: str) -> str:
    d = os.path.join(LIB_DIR, doc_id)
    os.makedirs(d, exist_ok=True)
    return d


def _save_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _download_url(url: str) -> Tuple[bytes, str]:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    content = r.content
    path = urlparse(url).path
    name = os.path.basename(path) or "downloaded"
    ct = r.headers.get("content-type", "")
    if "html" in ct and not name.lower().endswith((".html", ".htm")):
        name += ".html"
    return content, name


def _index_chunks(vstore: Any, chunks: List[Dict[str, Any]]) -> None:
    if not vstore or not chunks:
        return
    if hasattr(vstore, "upsert_texts"):
        for c in chunks:
            vstore.upsert_texts([c["text"]], ids=[c["id"]], meta=(c.get("metadata") or {}))
        return
    if hasattr(vstore, "add_texts"):
        for c in chunks:
            vstore.add_texts([c["text"]], meta=(c.get("metadata") or {}))
        return
    raise AttributeError("vstore must provide upsert_texts() or add_texts()")


def _map_reduce_summary(chunks: List[Dict[str, Any]], title: str, lang: str) -> Dict[str, Any]:
    if not INGEST_SUMMARIZE:
        return {}

    sys_msg = {
        "role": "system",
        "content": f"Take concise, factual notes. Language: ZZF0Z.",
    }

    bullets: List[str] = []
    for ch in chunks[:40]:
        prompt = [
            sys_msg,
            {"role": "user", "content": f"Korotko zakonspektiruy fragment (do 5 bulletov):\n\n{ch.get('text','')}"},
        ]
        try:
            snippet = LLM.chat(prompt, temperature=0.1, max_tokens=320)
        except Exception:
            snippet = ""
        if snippet:
            bullets.append(snippet.strip())

    map_notes = "\n".join(bullets)[:15000]

    reduce_prompt = [
        sys_msg,
        {
            "role": "user",
            "content": (
                f"Po konspektam sostav po dokumentu «{title}»:\n"
                "1) Rezyume 300–600 slov\n"
                "2) 10–20 tegov\n"
                "3) 10 Q&A kartochek\n\n"
                f"Konspekty:\n{map_notes}\n"
            ),
        },
    ]
    try:
        reduced = LLM.chat(reduce_prompt, temperature=0.2, max_tokens=1400)
    except Exception as e:
        reduced = f"Summarization error: ЗЗФ0З"

    return {"map_notes": map_notes, "reduced": reduced}


def _write_doc_bundle(doc_id: str, title: str, head_meta: Dict[str, Any], sections: List[Dict[str, Any]], chunks: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    d = _doc_dir(doc_id)
    _save_json(
        os.path.join(d, "meta.json"),
        {
            "doc_id": doc_id,
            "title": title,
            "dt_ingested": now_iso(),
            "mime": head_meta.get("mime"),
            "ext": head_meta.get("ext"),
            "lang": head_meta.get("lang"),
            "chunks_count": len(chunks),
            "version": doc_id,
        },
    )
    _save_json(os.path.join(d, "sections.json"), sections)
    _save_json(os.path.join(d, "chunks.json"), chunks)
    _save_json(os.path.join(d, "summary.json"), summary)


def _try_integrate_memories(app: Any, summary: Dict[str, Any]) -> None:
    if not summary:
        return
    mm = getattr(app, "memory_manager", None)
    if mm:
        try:
            mm.add_to_long_term(summary.get("reduced", ""))
        except Exception:
            pass


# -------------------------
# Worker infra
# -------------------------

_Q: "queue.Queue[Tuple[str, Dict[str, Any]]]" = queue.Queue()
_LOCK = threading.RLock()
_ACTIVE = False
_JOBS: Dict[str, JobState] = {}
_APP: Optional[Any] = None


def _set_active(val: bool) -> None:
    global _ACTIVE
    with _LOCK:
        _ACTIVE = val


def _get_active() -> bool:
    with _LOCK:
        return _ACTIVE


def _set_app(app: Any) -> None:
    global _APP
    if app is not None:
        _APP = app


def _get_app() -> Any:
    if _APP is not None:
        return _APP
    return current_app._get_current_object()


def _worker_loop() -> None:
    while True:
        job_id, job_payload = _Q.get()
        state = _JOBS.get(job_id)
        if not state:
            _Q.task_done()
            continue

        try:
            app = _get_app()
            vstore = getattr(app, "vstore", None)

            entries = job_payload["entries"]
            result_items: List[Dict[str, Any]] = []

            for idx, ent in enumerate(entries, start=1):
                state.status = "parsing"
                state.progress = round(((idx - 1) / max(1, len(entries))) * 10.0, 2)

                kind = ent.get("kind")
                if kind == "file":
                    raw = ent["raw"]
                    fname = ent["name"]
                else:
                    if not INGEST_ALLOW_URLS:
                        raise PermissionError("URL ingest disabled (INGEST_ALLOW_URLS=1 or ESTER_NET_INGEST_ALLOW=1).")
                    raw, fname = _download_url(ent["url"])

                if len(raw) > INGEST_MAX_BYTES:
                    result_items.append({"doc_id": "", "title": fname, "status": "error", "info": {"reason": f"too large ({len(raw)} bytes)"}})
                    continue

                doc_id = sha256_bytes(raw)
                doc_path = os.path.join(LIB_DIR, doc_id)

                if os.path.exists(os.path.join(doc_path, "meta.json")):
                    meta = _load_json(os.path.join(doc_path, "meta.json"), {})
                    result_items.append({"doc_id": doc_id, "title": meta.get("title", fname), "status": "skipped (dedup)"})
                    continue

                sections, full_text, head = detect_and_read(fname, raw)
                if not (full_text or "").strip():
                    result_items.append({"doc_id": doc_id, "title": fname, "status": "error", "info": {"reason": "empty text"}})
                    continue

                state.status = "chunking"
                chunks = chunk_document(doc_id, sections, head)

                state.status = "indexing"
                if vstore:
                    _index_chunks(vstore, chunks)

                state.status = "summarizing"
                summary = _map_reduce_summary(chunks, head.get("title") or fname, head.get("lang", "ru"))

                _write_doc_bundle(doc_id, head.get("title") or fname, head, sections, chunks, summary)
                _try_integrate_memories(app, summary)

                item_meta = {"doc_id": doc_id, "title": head.get("title") or fname, "dt_ingested": now_iso(), "mime": head.get("mime"), "lang": head.get("lang"), "chunks": len(chunks)}
                INDEX.add(item_meta)
                notify_done(item_meta["title"], doc_id)

                result_items.append({"doc_id": doc_id, "title": item_meta["title"], "status": "done", "info": {"chunks": len(chunks)}})
                state.progress = round((idx / max(1, len(entries))) * 100.0, 2)

            state.status = "done"
            state.results = result_items
            state.progress = 100.0

        except Exception as e:
            state.status = "error"
            state.error = str(e)

        finally:
            _Q.task_done()


def _ensure_worker_started(app: Any) -> None:
    if _get_active():
        _set_app(app)
        return
    with _LOCK:
        if _get_active():
            _set_app(app)
            return
        _set_app(app)
        t = threading.Thread(target=_worker_loop, name="ester-ingest-worker", daemon=True)
        t.start()
        _set_active(True)


# -------------------------
# Flask Blueprint
# -------------------------

ingest_bp = Blueprint("ingest", __name__, url_prefix="/ingest")


@ingest_bp.post("/upload")
def ingest_upload():
    if "files" not in request.files:
        return jsonify({"ok": False, "error": "No files part"}), 400
    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "error": "Empty files list"}), 400

    entries: List[Dict[str, Any]] = []
    for f in files:
        raw = f.read()
        entries.append({"kind": "file", "name": f.filename, "raw": raw})

    job_id = uuid.uuid4().hex
    _JOBS[job_id] = JobState(job_id, [{"source": e.get("name"), "kind": "file"} for e in entries])

    app = current_app._get_current_object()
    _ensure_worker_started(app)
    _Q.put((job_id, {"entries": entries}))
    return jsonify({"ok": True, "job_id": job_id})


@ingest_bp.post("/urls")
def ingest_urls():
    if not INGEST_ALLOW_URLS:
        return jsonify({"ok": False, "error": "URL ingest disabled"}), 403

    data = request.get_json(silent=True) or {}
    urls = data.get("urls") or []
    if not urls:
        return jsonify({"ok": False, "error": "Empty urls"}), 400

    entries = [{"kind": "url", "url": u} for u in urls]
    job_id = uuid.uuid4().hex
    _JOBS[job_id] = JobState(job_id, [{"source": e.get("url"), "kind": "url"} for e in entries])

    app = current_app._get_current_object()
    _ensure_worker_started(app)
    _Q.put((job_id, {"entries": entries}))
    return jsonify({"ok": True, "job_id": job_id})


@ingest_bp.get("/status/<job_id>")
def ingest_status(job_id: str):
    st = _JOBS.get(job_id)
    if not st:
        return jsonify({"ok": False, "error": "job not found"}), 404
    return jsonify({"ok": True, "job": st.to_dict()})


@ingest_bp.get("/list")
def ingest_list():
    try:
        limit = int(request.args.get("limit", "50"))
    except Exception:
        limit = 50
    return jsonify({"ok": True, "items": INDEX.list(limit)})


@ingest_bp.get("/<doc_id>")
def ingest_get(doc_id: str):
    d = os.path.join(LIB_DIR, doc_id)
    if not os.path.isdir(d):
        return jsonify({"ok": False, "error": "doc not found"}), 404
    meta = _load_json(os.path.join(d, "meta.json"), {})
    summary = _load_json(os.path.join(d, "summary.json"), {})
    return jsonify({"ok": True, "doc_id": doc_id, "meta": meta, "summary": summary})


@ingest_bp.delete("/<doc_id>")
def ingest_delete(doc_id: str):
    d = os.path.join(LIB_DIR, doc_id)
    if not os.path.isdir(d):
        return jsonify({"ok": False, "error": "doc not found"}), 404
    shutil.rmtree(d, ignore_errors=True)
    INDEX.delete(doc_id)
    return jsonify({"ok": True, "deleted": doc_id})


def register_ingestion_routes(app: Any) -> None:
    app.register_blueprint(ingest_bp)