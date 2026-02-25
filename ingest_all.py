# -*- coding: utf-8 -*-
from __future__ import annotations

"""ingest_all.py - “proglotit vse” iz papki proekta i polozhit v vstore.

What improved:
- net zhestkogo D:\... - root beretsya iz argumenta/tekuschey papki;
- net zavisimosti ot chromadb (po umolchaniyu ispolzuem vector_store.VectorStore);
- idempotentnost: determinirovannye chunk_id (povtornyy progon ne plodit dubley);
- normalnaya rabota s kodirovkami (utf-8/utf-16/cp1251 i t.p.);
- akkuratnyy chanking + metadannye (source, file_sha256, chunk_index, size, mtime).

Zapusk (PowerShell):
  python .\ingest_all.py --root D:\ester-project"""

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DEFAULT_IGNORE_DIRS = {
    ".git", "__pycache__", "venv", "env", "node_modules", ".idea", ".vscode",
    "tmp", "chroma", "vectors", ".pytest_cache", ".mypy_cache",
}
DEFAULT_IGNORE_FILES = {
    ".DS_Store", "package-lock.json",
}
DEFAULT_EXTS = {".md", ".txt", ".jsonl", ".py", ".json", ".yaml", ".yml"}
DEFAULT_MAX_CHARS = 1800
DEFAULT_OVERLAP = 200

try:
    from vector_store import VectorStore  # type: ignore
except Exception:  # pragma: no cover
    VectorStore = None  # type: ignore


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1251", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def _chunk_text(text: str, *, max_chars: int, overlap: int) -> List[str]:
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    step = max(1, max_chars - overlap)
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + max_chars)
        k = text.rfind("\n", i, j)
        if k > i + int(max_chars * 0.6):
            j = k
        ch = text[i:j].strip()
        if ch:
            chunks.append(ch)
        i += step
    return chunks


def _parse_jsonl(text: str) -> List[str]:
    out: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue

        if isinstance(data, dict) and "user" in data and "text" in data:
            ts = float(data.get("ts", 0) or 0)
            dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "unknown"
            user = str(data.get("user", "Unknown"))
            msg = str(data.get("text", ""))
            out.append(f"[Dialog {dt}] {user}: {msg}".strip())
            continue

        if isinstance(data, dict) and "text" in data:
            out.append(str(data.get("text", "")).strip())
            continue

        try:
            out.append(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    return [x for x in out if x]


def _safe_relpath(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root)
    except Exception:
        return path


def _vstore_upsert_per_item(vstore: Any, texts: Sequence[str], ids: Sequence[str], metas: Sequence[Dict[str, Any]]) -> None:
    if not texts:
        return
    if len(texts) != len(ids) or len(texts) != len(metas):
        raise ValueError("texts/ids/metas must have same length")

    if hasattr(vstore, "bulk_add"):
        vstore.bulk_add([(ids[i], texts[i], metas[i]) for i in range(len(texts))])
        return

    if hasattr(vstore, "upsert_texts"):
        for i in range(len(texts)):
            vstore.upsert_texts([texts[i]], ids=[ids[i]], meta=metas[i])
        return

    if hasattr(vstore, "add_texts"):
        for i in range(len(texts)):
            vstore.add_texts([texts[i]], meta=metas[i])
        return

    raise AttributeError("vstore must provide bulk_add() or upsert_texts() or add_texts()")


@dataclass
class Stats:
    files_seen: int = 0
    files_ingested: int = 0
    chunks_upserted: int = 0
    bytes_read: int = 0
    errors: int = 0


def iter_files(root: str, exts: set[str], ignore_dirs: set[str], ignore_files: set[str]) -> Iterable[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        for fn in filenames:
            if fn in ignore_files:
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext not in exts:
                continue
            yield os.path.join(dirpath, fn)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.getcwd(), help="Root to scan (default current folder)")
    ap.add_argument("--exts", default=",".join(sorted(DEFAULT_EXTS)), help="List of extensions separated by commas")
    ap.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    ap.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    ap.add_argument("--no-jsonl", action="store_true", help="Ne parsit jsonl spetsialnym obrazom")
    ap.add_argument("--dry-run", action="store_true", help="Don't write anything, just show statistics")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    exts = {("." + e.lstrip(".")).lower() for e in args.exts.split(",") if e.strip()}
    ignore_dirs = set(DEFAULT_IGNORE_DIRS)
    ignore_files = set(DEFAULT_IGNORE_FILES)

    if VectorStore is None:
        print("yRRsch vector_store.po not found/not imported. Make sure he's near ingest_all.po", file=sys.stderr)
        return 2

    vstore = VectorStore()
    st = Stats()
    t0 = time.perf_counter()

    print(f"[ingest_all] root={root}")
    print(f"[ingest_all] exts={sorted(exts)}")
    print(f"[ingest_all] db={getattr(vstore, 'db_path', '?')} collection={getattr(vstore, 'collection_name', '?')}")
    if args.dry_run:
        print("[ingest_all] DRY RUN — zapisi v vstore NE budet")

    for path in iter_files(root, exts, ignore_dirs, ignore_files):
        st.files_seen += 1
        try:
            raw = _read_file_bytes(path)
            st.bytes_read += len(raw)
            rel = _safe_relpath(path, root)
            ext = os.path.splitext(path)[1].lower()
            mtime = os.path.getmtime(path)

            file_sha = _sha256_bytes(raw)
            text = _decode_text(raw)

            if ext == ".jsonl" and not args.no_jsonl:
                docs = _parse_jsonl(text)
                chunks: List[str] = []
                for d in docs:
                    chunks.extend(_chunk_text(d, max_chars=args.max_chars, overlap=args.overlap))
            else:
                chunks = _chunk_text(text, max_chars=args.max_chars, overlap=args.overlap)

            chunks = [c for c in chunks if c.strip()]
            if not chunks:
                continue

            ids: List[str] = []
            metas: List[Dict[str, Any]] = []
            for i, ch in enumerate(chunks):
                cid = hashlib.sha256(f"{file_sha}:{i}".encode("utf-8")).hexdigest()
                ids.append(cid)
                metas.append(
                    {
                        "source": rel,
                        "type": "auto_ingest",
                        "ext": ext,
                        "file_sha256": file_sha,
                        "chunk_index": i,
                        "file_mtime": mtime,
                        "file_size": len(raw),
                        "ingested_ts": time.time(),
                    }
                )

            if not args.dry_run:
                _vstore_upsert_per_item(vstore, chunks, ids, metas)

            st.files_ingested += 1
            st.chunks_upserted += len(chunks)

            if st.files_ingested % 25 == 0:
                dt = time.perf_counter() - t0
                speed = st.bytes_read / max(1e-9, dt) / (1024 * 1024)
                print(f"[ingest_all] files={st.files_ingested} chunks={st.chunks_upserted} read={st.bytes_read/1e6:.1f}MB ~{speed:.1f}MB/s")

        except Exception as e:
            st.errors += 1
            print(f"[ERR] {path}: {e}", file=sys.stderr)

    dt = time.perf_counter() - t0
    print("")
    print("[ingest_all] DONE")
    print(f"  files_seen    = {st.files_seen}")
    print(f"  files_ingested= {st.files_ingested}")
    print(f"  chunks_upsert = {st.chunks_upserted}")
    print(f"  bytes_read    = {st.bytes_read}")
    print(f"  errors        = {st.errors}")
    print(f"  elapsed_sec   = {dt:.2f}")
    return 0 if st.errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())