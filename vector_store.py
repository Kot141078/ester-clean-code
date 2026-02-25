# -*- coding: utf-8 -*-
from __future__ import annotations

"""VectorStore dlya Ester: SQLite + FTS5 (leksika) + optsionalnye embeddingi (sentence-transformers).

Yavnyy most (kibernetika / Ashby):
- ustoychivost trebuet raznoobraziya kanalov nablyudeniya → gibrid (FTS + embeddings), a ne “odna knopka”.

Skrytye mosty:
- Cover&Thomas: ne polagatsya na odin korrelirovannyy signal (leksika or semantika).
- Jaynes: luchshe chestnaya aposteriornaya smes signalov, chem “vera v odnu model”.

Zemnoy abzats:
Eto ne “zapisnaya knizhka”, a zhurnal na sklade: tranzaktsii, WAL, i bystryy indeks po slovam.
Kogda svet morgnul - dannye ne dolzhny prevraschatsya v kashu."""

import json
import logging
import os
import re
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:  # pragma: no cover
    SentenceTransformer = None  # type: ignore


def _now() -> float:
    return time.time()


def _tok(s: str) -> List[str]:
    return re.findall(r"[0-9A-Za-zA-Yaa-yaEe]+", (s or "").lower())


def _safe_match_query(user_query: str) -> str:
    terms = _tok(user_query)
    if not terms:
        return ""
    quoted = ['"' + t.replace('"', '""') + '"' for t in terms]
    return " OR ".join(quoted)


def _json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return "{}"


def _json_loads(s: str) -> Dict[str, Any]:
    try:
        v = json.loads(s) if s else {}
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _env_path(*keys: str, default: str = "") -> str:
    for k in keys:
        v = os.environ.get(k, "")
        if v:
            return v
    return default


class VectorStore:
    """
    Kontrakt:
      - search(query, k=5) -> List[{"id","text","score","meta"}]
      - add_texts(texts, meta=None) -> ids
      - upsert_texts(texts, ids=None, meta=None) -> ids
      - delete(ids) -> int
      - size() -> int
    """

    def __init__(
        self,
        collection_name: str = "ester",
        persist_dir: str = "",
        db_name: str = "",
        use_embeddings: bool = True,
        embeddings_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        hybrid_alpha: float = 0.55,
        topn_default: int = 50,
        embeddings_api_base: str = "",
        embeddings_api_key: str = "",
        use_local: Optional[bool] = None,
        **legacy_kwargs: Any,
    ):
        # Legacy compat: older call-sites may pass remote embedding args.
        # This store only supports local sentence-transformers embeddings.
        _ = embeddings_api_base, embeddings_api_key, legacy_kwargs
        if use_local is False:
            use_embeddings = False

        # --- puti (po tvoemu .env) ---
        if not persist_dir:
            persist_dir = _env_path(
                "ESTER_VECTOR_DIR",  # D:\ester-project\vstore\vectors
                default="",
            )
        if not persist_dir:
            vroot = _env_path("ESTER_VSTORE_ROOT", default="")
            if vroot:
                persist_dir = os.path.join(vroot, "vectors")
        if not persist_dir:
            data_root = _env_path("ESTER_DATA_ROOT", "PERSIST_DIR", default=os.path.join(os.getcwd(), "data"))
            persist_dir = os.path.join(data_root, "vector_store")

        os.makedirs(persist_dir, exist_ok=True)

        # db_name: in your .env ESTER_VECTOR_DB=chroma (legacy). It doesn't break, just use it.
        if not db_name:
            db_name = os.environ.get("ESTER_VECTOR_DB", "").strip()
        if not db_name or db_name.lower() in ("chroma", "chromadb", "vectors", "vector", "db"):
            db_name = "ester_store.sqlite"
        if not db_name.lower().endswith(".sqlite"):
            db_name = db_name + ".sqlite"

        self.db_path = os.path.join(persist_dir, db_name)
        self.collection_name = collection_name
        self.topn_default = int(os.environ.get("ESTER_VECTOR_TOPN", str(topn_default)))

        env_alpha = os.environ.get("ESTER_VECTOR_ALPHA")
        if env_alpha is not None:
            try:
                hybrid_alpha = float(env_alpha)
            except Exception:
                pass
        self.hybrid_alpha = max(0.0, min(1.0, float(hybrid_alpha)))

        env_use = os.environ.get("USE_EMBEDDINGS")
        if env_use is not None:
            use_embeddings = str(env_use).strip().lower() not in ("0", "false", "no", "off")
        self.use_embeddings = bool(use_embeddings) and (SentenceTransformer is not None) and (np is not None)

        model_name = (
            os.environ.get("ESTER_EMBED_MODEL")
            or os.environ.get("EMBEDDINGS_MODEL")
            or embeddings_model
        )
        model_name = str(model_name or "").strip() or "all-MiniLM-L6-v2"
        if model_name.lower().startswith("sentence-transformers/"):
            model_name = model_name.split("/", 1)[1]
        self._emb_model_name = model_name
        self._emb_model = None

        self._conn = self._connect()
        self._has_fts = self._ensure_schema()
        self.path = os.path.join(persist_dir, f"{self.collection_name}.json")
        self._ensure_legacy_json()

    # ---------- DB ----------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA temp_store=MEMORY;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("PRAGMA busy_timeout=5000;")
        except Exception:
            pass
        return conn

    def _ensure_schema(self) -> bool:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS docs (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                collection TEXT NOT NULL,
                text TEXT NOT NULL,
                meta_json TEXT NOT NULL,
                created REAL NOT NULL,
                updated REAL NOT NULL
            );
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_collection ON docs(collection);")

        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                rowid INTEGER PRIMARY KEY,
                dim INTEGER NOT NULL,
                vec BLOB NOT NULL,
                FOREIGN KEY(rowid) REFERENCES docs(rowid) ON DELETE CASCADE
            );
            """
        )

        has_fts = True
        try:
            self._conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts
                USING fts5(
                    text,
                    collection UNINDEXED,
                    content='docs',
                    content_rowid='rowid',
                    tokenize='unicode61'
                );
                """
            )
            self._conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON docs BEGIN
                    INSERT INTO docs_fts(rowid, text, collection) VALUES (new.rowid, new.text, new.collection);
                END;
                """
            )
            self._conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON docs BEGIN
                    INSERT INTO docs_fts(docs_fts, rowid, text, collection) VALUES('delete', old.rowid, old.text, old.collection);
                END;
                """
            )
            self._conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON docs BEGIN
                    INSERT INTO docs_fts(docs_fts, rowid, text, collection) VALUES('delete', old.rowid, old.text, old.collection);
                    INSERT INTO docs_fts(rowid, text, collection) VALUES (new.rowid, new.text, new.collection);
                END;
                """
            )
        except Exception as e:
            has_fts = False
            logging.warning(f"[VectorStore] FTS5 nedostupen, fallback LIKE: {e}")

        return has_fts

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    # ---------- Embeddings ----------
    def _get_embedder(self):
        if not self.use_embeddings:
            return None
        if self._emb_model is not None:
            return self._emb_model
        try:
            self._emb_model = SentenceTransformer(self._emb_model_name)  # type: ignore
        except Exception as e:
            logging.warning(f"[VectorStore] embeddings model '{self._emb_model_name}' ne zagruzilas: {e}")
            self._emb_model = None
            self.use_embeddings = False
        return self._emb_model

    @staticmethod
    def _pack_vec(vec) -> bytes:
        return np.asarray(vec, dtype=np.float32).tobytes()  # type: ignore

    @staticmethod
    def _unpack_vec(blob: bytes, dim: int):
        return np.frombuffer(blob, dtype=np.float32, count=dim)  # type: ignore

    # ---------- Legacy JSON compat ----------
    def _ensure_legacy_json(self) -> None:
        if os.path.exists(self.path):
            return
        seed_id = "seed_" + uuid.uuid4().hex[:8]
        payload = {
            "docs": {
                seed_id: {
                    "id": seed_id,
                    "text": "seed",
                    "meta": {"compat": True},
                }
            },
            "alias_map": {},
        }
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    def _legacy_read(self) -> Dict[str, Any]:
        self._ensure_legacy_json()
        try:
            return json.loads(open(self.path, "r", encoding="utf-8").read() or "{}")
        except Exception:
            return {"docs": {}, "alias_map": {}}

    def _legacy_write(self, payload: Dict[str, Any]) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    def _legacy_upsert(self, ids: List[str], texts: List[str], meta: Dict[str, Any]) -> None:
        payload = self._legacy_read()
        docs = payload.get("docs")
        if not isinstance(docs, dict):
            docs = {}
            payload["docs"] = docs
        for doc_id, txt in zip(ids, texts):
            docs[str(doc_id)] = {
                "id": str(doc_id),
                "text": str(txt or ""),
                "meta": dict(meta or {}),
            }
        self._legacy_write(payload)

    def _legacy_delete(self, ids: List[str]) -> None:
        if not ids:
            return
        payload = self._legacy_read()
        docs = payload.get("docs")
        if not isinstance(docs, dict):
            return
        for doc_id in ids:
            docs.pop(str(doc_id), None)
        self._legacy_write(payload)

    # ---------- CRUD ----------
    def add_texts(self, texts: List[str], meta: Optional[Dict[str, Any]] = None) -> List[str]:
        meta = dict(meta or {})
        ids: List[str] = []
        now = _now()

        self._conn.execute("BEGIN IMMEDIATE;")
        try:
            for txt in texts:
                doc_id = uuid.uuid4().hex
                ids.append(doc_id)

                s = str(txt or "")
                # Fuse for “??????” (usually this is shell/pipe encoding)
                if s and s.count("?") >= max(8, int(len(s) * 0.25)):
                    logging.warning("[VectorStore] text looks mojibake (many '?'). Check PowerShell $OutputEncoding / UTF-8 pipe.")

                self._conn.execute(
                    "INSERT INTO docs(id, collection, text, meta_json, created, updated) VALUES (?, ?, ?, ?, ?, ?);",
                    (doc_id, self.collection_name, s, _json_dumps(meta), now, now),
                )
            self._conn.execute("COMMIT;")
        except Exception:
            self._conn.execute("ROLLBACK;")
            raise

        if self.use_embeddings:
            self._ensure_embeddings(ids)
        self._legacy_upsert(ids, [str(t or "") for t in texts], meta)

        return ids

    def upsert_texts(self, texts: List[str], ids: Optional[List[str]] = None, meta: Optional[Dict[str, Any]] = None) -> List[str]:
        meta = dict(meta or {})
        now = _now()
        if ids is None:
            ids = [uuid.uuid4().hex for _ in texts]
        if len(ids) != len(texts):
            raise ValueError("ids length must match texts length")

        self._conn.execute("BEGIN IMMEDIATE;")
        try:
            for doc_id, txt in zip(ids, texts):
                self._conn.execute(
                    """
                    INSERT INTO docs(id, collection, text, meta_json, created, updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        collection=excluded.collection,
                        text=excluded.text,
                        meta_json=excluded.meta_json,
                        updated=excluded.updated;
                    """,
                    (doc_id, self.collection_name, str(txt or ""), _json_dumps(meta), now, now),
                )
            self._conn.execute("COMMIT;")
        except Exception:
            self._conn.execute("ROLLBACK;")
            raise

        if self.use_embeddings:
            self._ensure_embeddings(ids)
        self._legacy_upsert([str(x) for x in ids], [str(t or "") for t in texts], meta)

        return ids

    def delete(self, ids: List[str]) -> int:
        if not ids:
            return 0
        self._conn.execute("BEGIN IMMEDIATE;")
        try:
            cur = self._conn.execute(
                f"DELETE FROM docs WHERE collection=? AND id IN ({','.join(['?'] * len(ids))});",
                (self.collection_name, *ids),
            )
            self._conn.execute("COMMIT;")
            self._legacy_delete(ids)
            return int(cur.rowcount or 0)
        except Exception:
            self._conn.execute("ROLLBACK;")
            raise

    def size(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM docs WHERE collection=?;", (self.collection_name,)).fetchone()
        return int(row["n"]) if row else 0

    def _ensure_embeddings(self, ids: List[str]) -> None:
        model = self._get_embedder()
        if model is None:
            return

        q = f"""
        SELECT d.rowid, d.text
        FROM docs d
        LEFT JOIN embeddings e ON e.rowid=d.rowid
        WHERE d.collection=? AND d.id IN ({','.join(['?'] * len(ids))}) AND e.rowid IS NULL;
        """
        rows = self._conn.execute(q, (self.collection_name, *ids)).fetchall()
        if not rows:
            return

        texts = [r["text"] for r in rows]
        try:
            vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)  # type: ignore
        except Exception as e:
            logging.warning(f"[VectorStore] embeddings encode upal: {e}")
            return

        self._conn.execute("BEGIN IMMEDIATE;")
        try:
            for r, v in zip(rows, vecs):
                dim = int(v.shape[0])
                blob = self._pack_vec(v)
                self._conn.execute(
                    "INSERT OR REPLACE INTO embeddings(rowid, dim, vec) VALUES (?, ?, ?);",
                    (int(r["rowid"]), dim, sqlite3.Binary(blob)),
                )
            self._conn.execute("COMMIT;")
        except Exception:
            self._conn.execute("ROLLBACK;")
            raise

    # ---------- Search ----------
    def _lexical_candidates(self, query: str, topn: int) -> List[Tuple[int, str, str, Dict[str, Any], float]]:
        topn = max(1, int(topn))
        if not query.strip():
            return []

        if self._has_fts:
            match = _safe_match_query(query)
            if not match:
                return []
            try:
                rows = self._conn.execute(
                    """
                    SELECT d.rowid AS rowid, d.id AS id, d.text AS text, d.meta_json AS meta_json,
                           bm25(docs_fts) AS bm
                    FROM docs_fts
                    JOIN docs d ON docs_fts.rowid = d.rowid
                    WHERE d.collection=? AND docs_fts MATCH ?
                    ORDER BY bm
                    LIMIT ?;
                    """,
                    (self.collection_name, match, topn),
                ).fetchall()
            except Exception as e:
                logging.warning(f"[VectorStore] FTS MATCH upal, fallback LIKE: {e}")
                rows = []

            out: List[Tuple[int, str, str, Dict[str, Any], float]] = []
            for r in rows:
                bm = float(r["bm"]) if r["bm"] is not None else 0.0
                lex = 1.0 / (1.0 + max(0.0, bm))
                out.append((int(r["rowid"]), str(r["id"]), str(r["text"]), _json_loads(r["meta_json"]), float(lex)))
            return out

        terms = _tok(query)
        if not terms:
            return []
        like = f"%{terms[0]}%"
        rows = self._conn.execute(
            """
            SELECT rowid, id, text, meta_json
            FROM docs
            WHERE collection=? AND lower(text) LIKE ?
            ORDER BY updated DESC
            LIMIT ?;
            """,
            (self.collection_name, like, topn),
        ).fetchall()

        out2: List[Tuple[int, str, str, Dict[str, Any], float]] = []
        for r in rows:
            t = (r["text"] or "").lower()
            hits = sum(1 for w in terms if w in t)
            lex = hits / max(1, len(terms))
            out2.append((int(r["rowid"]), str(r["id"]), str(r["text"]), _json_loads(r["meta_json"]), float(lex)))
        return out2

    def _semantic_scores(self, query: str, rowids: Sequence[int]) -> Dict[int, float]:
        model = self._get_embedder()
        if model is None or np is None or not rowids:
            return {}

        try:
            qv = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]  # type: ignore
        except Exception as e:
            logging.warning(f"[VectorStore] query embedding encode upal: {e}")
            return {}

        q = f"SELECT rowid, dim, vec FROM embeddings WHERE rowid IN ({','.join(['?'] * len(rowids))});"
        rows = self._conn.execute(q, tuple(int(x) for x in rowids)).fetchall()
        vec_map: Dict[int, Tuple[int, bytes]] = {int(r["rowid"]): (int(r["dim"]), bytes(r["vec"])) for r in rows}

        out: Dict[int, float] = {}
        for rid in rowids:
            pack = vec_map.get(int(rid))
            if not pack:
                out[int(rid)] = 0.0
                continue
            dim, blob = pack
            dv = self._unpack_vec(blob, dim)
            out[int(rid)] = float(np.dot(dv, qv))  # normalize → dot≈cos
        return out

    def search(self, query: str, k: int = 5, topn: Optional[int] = None) -> List[Dict[str, Any]]:
        k = max(1, int(k))
        topn = int(topn or self.topn_default)
        topn = max(topn, k)

        cands = self._lexical_candidates(query, topn=topn)
        if not cands:
            return []

        rowids = [c[0] for c in cands]
        sem = self._semantic_scores(query, rowids) if self.use_embeddings else {}
        alpha = self.hybrid_alpha

        out: List[Dict[str, Any]] = []
        for (rid, doc_id, text, meta, lex) in cands:
            s = float(sem.get(rid, 0.0))
            score = (1.0 - alpha) * float(lex) + alpha * float(s)
            out.append(
                {
                    "id": doc_id,
                    "text": text,
                    "score": float(score),
                    "meta": meta,
                    "lex_score": float(lex),
                    "sem_score": float(s),
                }
            )

        out.sort(key=lambda x: x["score"], reverse=True)
        return out[:k]

    # aliases
    def query(self, query: str, k: int = 5, **kwargs) -> List[Dict[str, Any]]:
        return self.search(query, k=k, topn=kwargs.get("topn") or kwargs.get("top_n"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "db_path": self.db_path,
            "collection": self.collection_name,
            "has_fts": self._has_fts,
            "use_embeddings": self.use_embeddings,
            "embeddings_model": self._emb_model_name if self.use_embeddings else None,
            "size": self.size(),
            "alpha": self.hybrid_alpha,
            "topn_default": self.topn_default,
            "updated_at": _now(),
        }
