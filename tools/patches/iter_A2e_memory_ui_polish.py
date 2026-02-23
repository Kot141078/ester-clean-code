# -*- coding: utf-8 -*-
"""
ITER A2e:
- UI limits: /memory/list and /memory/search must respect limit/k AFTER merge+dedup.
- Strip vectors by default: remove vec + vec_legacy + common embedding keys unless ?vec=1.
- Timeline dedup within day (json+chroma) so “same moment” does not double-count.
- Warn about suspicious persist dirs containing %VAR% (common “two homes” symptom).

YaVNYY MOST: c=a+b — pamyat ne dolzhna raspukhat ili “ischezat” iz-za skleyki istochnikov.
SKRYTYE MOSTY:
  - Ashby: variety (neskolko khranilisch) polezno, no bez upravlyayuschego ogranicheniya (limitov) prevraschaetsya v shum.
  - Cover&Thomas: limity + dedup = kontrol kanala (ne taschim megabayty vec_legacy v UI).
ZEMNOY ABZATs:
  Eto kak kardiomonitor: vazhno ne tolko “mnogo signalov”, a chtoby chastota/shum byli pod kontrolem,
  inache vrach (UI) vidit kashu vmesto ritma.
"""
from __future__ import annotations

import sys, time, shutil, py_compile
from pathlib import Path

ROOT = Path(r"D:\ester-project").resolve()
sys.path.insert(0, str(ROOT))

def backup(p: Path) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    b = p.with_suffix(p.suffix + f".bak_A2e_{ts}")
    shutil.copy2(str(p), str(b))
    return b

def write_text(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

CHROMA_ADAPTER = ROOT / "modules" / "memory" / "chroma_adapter.py"
MEMORY_ROUTES  = ROOT / "routes" / "memory_routes.py"

for p in (CHROMA_ADAPTER, MEMORY_ROUTES):
    if not p.exists():
        raise SystemExit(f"Missing: {p}")

b1 = backup(CHROMA_ADAPTER)
b2 = backup(MEMORY_ROUTES)

chroma_adapter_new = r'''# -*- coding: utf-8 -*-
from __future__ import annotations

import os, time, uuid, logging, re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- silence noisy telemetry logs (harmless but annoying) ---
for _ln in ("chromadb.telemetry", "chromadb.telemetry.product", "chromadb.telemetry.product.posthog"):
    try:
        logging.getLogger(_ln).setLevel(logging.CRITICAL)
    except Exception:
        pass

try:
    import chromadb  # type: ignore
    from chromadb.config import Settings  # type: ignore
    from chromadb.utils import embedding_functions  # type: ignore
except Exception:
    chromadb = None  # type: ignore
    Settings = None  # type: ignore
    embedding_functions = None  # type: ignore


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()

def _looks_unexpanded(x: str) -> bool:
    try:
        return bool(re.search(r"%[A-Za-z_][A-Za-z0-9_]*%", x or "")) or ("${" in (x or ""))
    except Exception:
        return False

def _expand_path(p: str) -> str:
    p = (p or "").strip()
    if not p:
        return ""
    p2 = os.path.expandvars(os.path.expanduser(p))
    # esli ostalis %VAR% — schitaem “pusto”, chtoby ne plodit musor
    if _looks_unexpanded(p2):
        return ""
    return p2

def _score_from_distance(d: Any) -> float:
    try:
        x = float(d)
        return 1.0 / (1.0 + max(0.0, x))
    except Exception:
        return 0.0

def _meta_get_ts(meta: Any) -> Optional[int]:
    try:
        if isinstance(meta, dict):
            v = meta.get("time") or meta.get("ts") or meta.get("timestamp")
            if v is None:
                return None
            return int(v)
    except Exception:
        return None
    return None

def _split_dirs(value: str) -> List[str]:
    s = (value or "").strip()
    if not s:
        return []
    parts = re.split(r"[;,\n]+", s)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        out.append(p)
    return out

def _candidate_roots(project_root: Optional[str]) -> List[Path]:
    roots: List[Path] = []
    if project_root:
        roots.append(Path(project_root))
    roots.append(Path(os.getcwd()))

    # env roots (expanded; unexpanded ignored)
    for envk in ("CHROMA_PERSIST_DIR","ESTER_VSTORE_ROOT","ESTER_HOME","ESTER_STATE_DIR"):
        v = _expand_path(_env(envk, ""))
        if v:
            roots.append(Path(v))
            roots.append(Path(v) / "chroma")
            roots.append(Path(v) / "vstore" / "chroma")

    # common
    if project_root:
        pr = Path(project_root)
        roots.append(pr / "vstore" / "chroma")
        roots.append(pr / "data" / "vstore" / "chroma")

    # extra dirs:
    # - try expand per token (if that yields a real dir, prefer it)
    # - otherwise, allow literal path if it exists (even with %...% in name)
    for raw in _split_dirs(_env("CHROMA_EXTRA_DIRS", "")):
        exp = os.path.expandvars(os.path.expanduser(raw))
        try:
            if exp and (not _looks_unexpanded(exp)) and Path(exp).exists():
                roots.append(Path(exp))
                continue
        except Exception:
            pass
        roots.append(Path(raw))

    # uniq existing dirs
    uniq: List[Path] = []
    seen = set()
    for r in roots:
        try:
            rr = r.resolve()
        except Exception:
            continue
        if rr.exists() and rr.is_dir() and str(rr) not in seen:
            uniq.append(rr); seen.add(str(rr))
    return uniq

def _walk_find_sqlite(root: Path, max_depth: int = 6, max_hits: int = 50) -> List[Path]:
    """
    Faster than rglob on huge trees: bounded depth + bounded hits.
    Returns directories that contain chroma.sqlite3.
    """
    hits: List[Path] = []
    root = root.resolve()
    try:
        root_parts = len(root.parts)
    except Exception:
        root_parts = 0

    for dirpath, dirnames, filenames in os.walk(str(root)):
        try:
            p = Path(dirpath)
            depth = len(p.parts) - root_parts
            if depth > max_depth:
                dirnames[:] = []
                continue
        except Exception:
            pass

        if "chroma.sqlite3" in filenames:
            hits.append(Path(dirpath))
            if len(hits) >= max_hits:
                break
    return hits

def _find_sqlite_dirs(roots: List[Path]) -> List[Path]:
    hits: List[Path] = []
    for r in roots:
        try:
            hits.extend(_walk_find_sqlite(r, max_depth=int(_env("CHROMA_SCAN_DEPTH","6") or 6), max_hits=50))
        except Exception:
            pass
    uniq: List[Path] = []
    seen = set()
    for h in hits:
        try:
            hh = h.resolve()
        except Exception:
            continue
        if str(hh) not in seen:
            uniq.append(hh); seen.add(str(hh))
    return uniq

def _list_collection_names(client: Any) -> List[str]:
    try:
        cols = client.list_collections()
    except Exception:
        return []
    out: List[str] = []
    for c in cols or []:
        if isinstance(c, str):
            out.append(c)
        else:
            name = getattr(c, "name", None)
            if name:
                out.append(str(name))
            else:
                out.append(str(c))
    return out

def _get_collection(client: Any, name: str, ef: Any = None, create: bool = False):
    # read-only: try get_collection; create: get_or_create_collection
    if create:
        try:
            if ef is not None:
                return client.get_or_create_collection(name=name, embedding_function=ef)
            return client.get_or_create_collection(name=name)
        except TypeError:
            return client.get_or_create_collection(name=name)
        except Exception:
            return None

    # get existing
    try:
        if ef is not None:
            return client.get_collection(name=name, embedding_function=ef)
        return client.get_collection(name=name)
    except TypeError:
        try:
            return client.get_collection(name=name)
        except Exception:
            return None
    except Exception:
        return None

def _probe_counts(persist_dir: str, want_collection: str) -> Tuple[int, int]:
    """
    returns (want_count, best_any_count) for this persist dir.
    """
    if chromadb is None:
        return (0, 0)
    try:
        client = chromadb.PersistentClient(path=str(persist_dir), settings=Settings(anonymized_telemetry=False))
        names = _list_collection_names(client)
        want = 0
        best = 0
        for nm in names:
            try:
                coll = client.get_collection(name=nm)
                cnt = int(coll.count())
            except Exception:
                cnt = 0
            if cnt > best:
                best = cnt
            if nm == want_collection:
                want = cnt
        return (want, best)
    except Exception:
        return (0, 0)

class _Store:
    def __init__(self, persist_dir: str, collection: str, ef: Any, create: bool = False) -> None:
        self.persist_dir = persist_dir
        self.collection = collection
        self.client = None
        self.coll = None
        self.err = ""
        self.count = 0
        self.create = create
        self.suspicious = False
        try:
            self.suspicious = bool(re.search(r"%[A-Za-z_][A-Za-z0-9_]*%", persist_dir or ""))
        except Exception:
            self.suspicious = False

        if chromadb is None:
            self.err = "chromadb not installed"
            return
        try:
            self.client = chromadb.PersistentClient(path=str(persist_dir), settings=Settings(anonymized_telemetry=False))
            self.coll = _get_collection(self.client, collection, ef=ef, create=create)
            if self.coll is not None:
                try:
                    self.count = int(self.coll.count())
                except Exception:
                    self.count = 0
        except Exception as e:
            self.err = str(e)

    def ok(self) -> bool:
        return self.coll is not None

class MultiChromaUI:
    """
    Aggregates multiple Chroma stores.
    Read: search/list across all stores.
    Write: by default only to PRIMARY store (highest count for target collection), unless CHROMA_WRITE_ALL=1.
    """
    def __init__(self) -> None:
        self.project_root = _expand_path(_env("ESTER_PROJECT_ROOT","")) or os.getcwd()
        self.collection_name = _env("CHROMA_COLLECTION_UI", "ester_global") or "ester_global"
        self.embed_model = _env("MEM_EMBED_MODEL", "all-MiniLM-L6-v2") or "all-MiniLM-L6-v2"

        self._err = ""
        self.stores: List[_Store] = []
        self.primary: Optional[_Store] = None
        self._warnings: List[str] = []

        if chromadb is None:
            self._err = "chromadb not installed"
            return

        # embedding function (optional)
        ef = None
        no_embed = (_env("CHROMA_UI_NO_EMBED","0").lower() in ("1","true","yes","on"))
        if (embedding_functions is not None) and (not no_embed):
            try:
                ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=self.embed_model)
            except Exception:
                ef = None

        # candidates:
        # 1) explicit CHROMA_PERSIST_DIR (expanded)
        explicit = _expand_path(_env("CHROMA_PERSIST_DIR",""))
        candidates: List[str] = []
        if explicit:
            candidates.append(explicit)

        # 2) default derived
        vroot = _expand_path(_env("ESTER_VSTORE_ROOT",""))
        if vroot:
            candidates.append(os.path.join(vroot, "chroma"))
        home = _expand_path(_env("ESTER_STATE_DIR","")) or _expand_path(_env("ESTER_HOME",""))
        if home:
            candidates.append(os.path.join(home, "vstore", "chroma"))

        # 3) scan nearby for real chroma.sqlite3 (bounded)
        roots = _candidate_roots(self.project_root)
        dirs = _find_sqlite_dirs(roots)
        for d in dirs:
            candidates.append(str(d))

        # uniq existing
        uniq: List[str] = []
        seen = set()
        for c in candidates:
            try:
                p = Path(c).resolve()
            except Exception:
                continue
            if not p.exists() or not p.is_dir():
                continue
            s = str(p)
            if s not in seen:
                uniq.append(s); seen.add(s)

        if not uniq:
            # fallback: current cwd/vstore/chroma
            uniq = [str((Path(os.getcwd()) / "vstore" / "chroma").resolve())]

        # pick primary dir
        primary_dir = None
        if explicit:
            primary_dir = explicit
        else:
            best_want = -1
            best_any = -1
            best_dir = None
            for d in uniq[:50]:
                w, a = _probe_counts(d, self.collection_name)
                if w > best_want or (w == best_want and a > best_any):
                    best_want, best_any = w, a
                    best_dir = d
            primary_dir = best_dir or uniq[0]

        self._write_all = (_env("CHROMA_WRITE_ALL","0").lower() in ("1","true","yes","on"))

        # build stores
        for d in uniq[:50]:
            create = bool(d == primary_dir)  # only primary may create missing collection
            st = _Store(d, self.collection_name, ef=ef, create=create)
            if st.ok():
                self.stores.append(st)

        # choose primary among ok stores
        if self.stores:
            for st in self.stores:
                if st.persist_dir == primary_dir:
                    self.primary = st
                    break
            if self.primary is None:
                self.primary = max(self.stores, key=lambda s: int(getattr(s,"count",0) or 0))
        else:
            self._err = "no usable chroma stores found"

        # warnings
        try:
            sus = [s for s in self.stores if getattr(s, "suspicious", False)]
            if sus:
                self._warnings.append("suspicious_dir: some stores contain literal %VAR% in path (two-homes symptom).")
        except Exception:
            pass

    def available(self) -> bool:
        return bool(self.primary is not None and self.primary.ok())

    def total_count(self) -> int:
        try:
            return int(sum(int(s.count or 0) for s in self.stores))
        except Exception:
            return 0

    def warnings(self) -> List[str]:
        return list(self._warnings or [])

    def status(self) -> Dict[str, Any]:
        stores = []
        for s in self.stores:
            stores.append({
                "dir": s.persist_dir,
                "count": int(s.count or 0),
                "primary": bool(self.primary is not None and s.persist_dir == self.primary.persist_dir),
                "suspicious": bool(getattr(s, "suspicious", False)),
            })
        stores.sort(key=lambda x: int(x.get("count") or 0), reverse=True)
        out = {
            "ok": self.available(),
            "collection": self.collection_name,
            "embed_model": self.embed_model,
            "error": self._err,
            "total_count": self.total_count(),
            "warnings": self.warnings(),
            "stores": stores,
        }
        return out

    def add_record(self, type_: str, text: str, meta: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if not self.available():
            return None
        t = (text or "").strip()
        if not t:
            return None
        m = dict(meta or {})
        typ = (type_ or m.get("type") or "fact")
        now = int(time.time())
        m.setdefault("type", typ)
        m.setdefault("time", now)
        _id = f"ui_{uuid.uuid4().hex}"

        targets = self.stores if self._write_all else ([self.primary] if self.primary is not None else [])
        ok_any = False
        for st in targets:
            try:
                st.coll.add(documents=[t], metadatas=[m], ids=[_id])
                ok_any = True
            except Exception:
                pass

        if not ok_any:
            return None
        return {"id": _id, "type": typ, "text": t, "meta": m, "ts": now}

    def delete(self, rid: str) -> bool:
        rid = (rid or "").strip()
        if not rid:
            return False
        ok_any = False
        for st in self.stores:
            try:
                st.coll.delete(ids=[rid])
                ok_any = True
            except Exception:
                pass
        return ok_any

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []
        k = max(1, min(50, int(top_k or 5)))
        out: List[Dict[str, Any]] = []

        for st in self.stores:
            try:
                res = st.coll.query(
                    query_texts=[q],
                    n_results=k,
                    include=["documents","metadatas","distances","ids"],
                )
            except Exception:
                continue

            ids = (res.get("ids") or [[]])[0] or []
            docs = (res.get("documents") or [[]])[0] or []
            metas = (res.get("metadatas") or [[]])[0] or []
            dists = (res.get("distances") or [[]])[0] or []

            for i in range(min(len(ids), len(docs))):
                meta = metas[i] if i < len(metas) else {}
                dist = dists[i] if i < len(dists) else None
                ts = _meta_get_ts(meta)
                typ = ""
                try:
                    if isinstance(meta, dict):
                        typ = str(meta.get("type") or "")
                except Exception:
                    pass
                out.append({
                    "id": ids[i],
                    "type": typ or "fact",
                    "text": docs[i],
                    "meta": meta if isinstance(meta, dict) else {},
                    "ts": ts,
                    "_score": _score_from_distance(dist),
                    "_dir": st.persist_dir,
                })

        # merge sort: score desc, ts desc
        try:
            out.sort(key=lambda r: (float(r.get("_score") or 0.0), int(r.get("ts") or 0)), reverse=True)
        except Exception:
            pass

        # dedup across stores by (type,text,ts_bucket)
        seen = set()
        merged: List[Dict[str, Any]] = []
        for r in out:
            ts = int(r.get("ts") or 0)
            key = (str(r.get("type") or ""), (r.get("text") or "").strip(), ts // 5)
            if key in seen:
                continue
            seen.add(key)
            merged.append(r)
            if len(merged) >= k:
                break
        return merged

    def list_recent(self, type_filter: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        lim = max(1, min(5000, int(limit or 200)))
        lim_per_store = min(2000, max(200, lim * 3))

        out: List[Dict[str, Any]] = []

        for st in self.stores:
            ids: List[str] = []
            docs: List[str] = []
            metas: List[Any] = []
            res = None

            # 1) peek
            try:
                res = st.coll.peek(limit=lim_per_store)
            except TypeError:
                try:
                    res = st.coll.peek(lim_per_store)
                except Exception:
                    res = None
            except Exception:
                res = None

            if isinstance(res, dict) and res.get("ids") is not None:
                ids = res.get("ids") or []
                docs = res.get("documents") or []
                metas = res.get("metadatas") or []
            else:
                where = {"type": str(type_filter)} if type_filter else None
                try:
                    res = st.coll.get(include=["documents","metadatas","ids"], where=where, limit=lim_per_store)
                except TypeError:
                    try:
                        res = st.coll.get(include=["documents","metadatas","ids"], where=where)
                    except Exception:
                        res = None
                except Exception:
                    res = None

                if isinstance(res, dict):
                    ids = res.get("ids") or []
                    docs = res.get("documents") or []
                    metas = res.get("metadatas") or []

            for i in range(min(len(ids), len(docs))):
                meta = metas[i] if i < len(metas) else {}
                if type_filter and isinstance(meta, dict):
                    if str(meta.get("type") or "") != str(type_filter):
                        continue
                ts = _meta_get_ts(meta)
                typ = ""
                try:
                    if isinstance(meta, dict):
                        typ = str(meta.get("type") or "")
                except Exception:
                    pass
                out.append({
                    "id": ids[i],
                    "type": typ or "fact",
                    "text": docs[i],
                    "meta": meta if isinstance(meta, dict) else {},
                    "ts": ts,
                    "_dir": st.persist_dir,
                })

        # sort by ts desc
        try:
            out.sort(key=lambda r: int(r.get("ts") or 0), reverse=True)
        except Exception:
            pass

        # dedup across stores by (type,text,ts_bucket)
        seen = set()
        merged: List[Dict[str, Any]] = []
        for r in out:
            ts = int(r.get("ts") or 0)
            key = (str(r.get("type") or ""), (r.get("text") or "").strip(), ts // 5)
            if key in seen:
                continue
            seen.add(key)
            merged.append(r)
            if len(merged) >= lim:
                break
        return merged


_UI_SINGLETON: Optional[MultiChromaUI] = None
def get_chroma_ui() -> Optional[MultiChromaUI]:
    global _UI_SINGLETON
    if _UI_SINGLETON is None:
        try:
            _UI_SINGLETON = MultiChromaUI()
        except Exception:
            _UI_SINGLETON = None
    return _UI_SINGLETON
'''

memory_routes_new = r'''# -*- coding: utf-8 -*-
"""
routes/memory_routes.py — UI navigatsiya po pamyati (JSON + Chroma).

Ruchki:
- GET  /memory/list?type=&limit=200
- GET  /memory/search?q=&k=5
- GET  /memory/timeline?days=30&per_day=20&type=&src=auto|json|chroma|hybrid
- GET  /memory/status
- POST /memory/add
- POST /memory/forget
- POST /memory/snapshot

ENV:
- MEMORY_UI_BACKEND=auto|json|chroma|hybrid
- MEM_UI_DUAL_WRITE=1|0
"""
from __future__ import annotations

import os, time
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, render_template
from modules.memory import store

try:
    from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
except Exception:
    get_chroma_ui = None  # type: ignore

bp = Blueprint("memory_routes", __name__, url_prefix="/memory")

def _backend_mode() -> str:
    mode = (os.getenv("MEMORY_UI_BACKEND", "auto") or "auto").strip().lower()
    if mode not in ("auto","json","chroma","hybrid"):
        mode = "auto"
    if mode == "json":
        return "json"
    if get_chroma_ui is None:
        return "json"

    try:
        ch = get_chroma_ui()
    except Exception:
        ch = None

    if ch is None or not getattr(ch, "available", lambda: False)():
        return "json"

    # esli auto/hybrid i chroma pustaya — smysla net, ne putaem UI
    try:
        total = int(getattr(ch, "total_count", lambda: 0)() or 0)
    except Exception:
        total = 0
    if mode in ("auto","hybrid") and total <= 0:
        return "json"

    if mode == "chroma":
        return "chroma"
    if mode == "hybrid":
        return "hybrid"
    return "hybrid"

def _dual_write() -> bool:
    v = (os.getenv("MEM_UI_DUAL_WRITE", "1") or "1").strip().lower()
    return v not in ("0","false","no","off")

def _ts_bucket(r: dict, bucket_sec: int = 5) -> int:
    try:
        ts = int(r.get("ts") or r.get("_ts") or 0)
        return ts // bucket_sec
    except Exception:
        return 0

def _dedup_key(r: dict):
    return (str(r.get("type") or ""), (r.get("text") or "").strip(), _ts_bucket(r, 5))

def _dedup(items):
    seen = set()
    out = []
    for r in items:
        key = _dedup_key(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

def _maybe_strip_vectors(obj: dict) -> dict:
    # po umolchaniyu rezhem lyubye vektory/embeddingi v UI, chtoby ne gnat megabayty
    keep = (request.args.get("vec","0") or "0").strip().lower() in ("1","true","yes","on")
    if keep:
        return obj
    if not isinstance(obj, dict):
        return obj
    obj = dict(obj)
    for k in ("vec", "vec_legacy", "embedding", "emb", "vector", "vectors"):
        obj.pop(k, None)
    return obj

def _trim(items, limit: int):
    try:
        limit = int(limit)
    except Exception:
        limit = 200
    limit = max(1, limit)
    return (items or [])[:limit]

@bp.route("/status", methods=["GET"])
def status_():
    mode = _backend_mode()
    ch_status = None
    if get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if ch is not None:
                ch_status = ch.status()
        except Exception:
            ch_status = None
    return jsonify({"ok": True, "backend": mode, "chroma": ch_status})

@bp.route("/list", methods=["GET"])
def list_():
    t = request.args.get("type")
    limit = int((request.args.get("limit","200") or "200").strip() or 200)
    limit = max(1, min(1000, limit))
    mode = _backend_mode()

    items = []

    # oversample per source in hybrid to have enough after dedup
    lim_src = limit if mode != "hybrid" else min(2000, max(200, limit * 3))

    # chroma first
    if mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                for r in ch.list_recent(type_filter=t, limit=lim_src):
                    rr = dict(r); rr["_src"]="chroma"
                    rr = _maybe_strip_vectors(rr)
                    items.append(rr)
        except Exception:
            pass

    # json
    if mode in ("json","hybrid"):
        try:
            data = [r for r in store._MEM.values() if (not t or r.get("type") == t)]
            data.sort(key=lambda x: int(x.get("ts",0) or 0), reverse=True)
            data = data[:lim_src]
            for r in data:
                rr = dict(r); rr["_src"]="json"
                rr = _maybe_strip_vectors(rr)
                items.append(rr)
        except Exception:
            pass

    if mode == "hybrid":
        items = _dedup(items)
        items = _trim(items, limit)
    else:
        items = _trim(items, limit)

    return jsonify({"ok": True, "backend": mode, "count": len(items), "items": items})

@bp.route("/search", methods=["GET"])
def search_():
    q = (request.args.get("q","") or "").strip()
    k = int((request.args.get("k","5") or "5").strip() or 5)
    k = max(1, min(20, k))
    mode = _backend_mode()
    results = []

    # oversample in hybrid to have enough after dedup
    k_src = k if mode != "hybrid" else min(50, max(10, k * 3))

    if q and mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                for r in ch.search(q, top_k=k_src):
                    rr = dict(r); rr["_src"]="chroma"
                    rr = _maybe_strip_vectors(rr)
                    results.append(rr)
        except Exception:
            pass

    if q and mode in ("json","hybrid"):
        try:
            for r in store.query(q, top_k=k_src):
                rr = dict(r); rr["_src"]="json"
                rr = _maybe_strip_vectors(rr)
                results.append(rr)
        except Exception:
            pass

    if mode == "hybrid":
        results = _dedup(results)
        results = _trim(results, k)
    else:
        results = _trim(results, k)

    return jsonify({"ok": True, "backend": mode, "query": q, "k": k, "results": results})

@bp.route("/timeline", methods=["GET"])
def timeline_():
    days = int((request.args.get("days","30") or "30").strip() or 30)
    per_day = int((request.args.get("per_day","20") or "20").strip() or 20)
    t = request.args.get("type")
    src = (request.args.get("src","auto") or "auto").strip().lower()
    if src not in ("auto","json","chroma","hybrid"):
        src = "auto"

    mode = _backend_mode()
    if src != "auto":
        mode = src

    days = max(1, min(365, days))
    per_day = max(1, min(200, per_day))
    now = int(time.time())
    cutoff = now - days * 86400

    buckets = {}  # day -> list
    seen_per_day = {}  # day -> set(dedup_key)

    def put(day: str, rec: dict):
        arr = buckets.get(day)
        if arr is None:
            arr = []
            buckets[day] = arr
        s = seen_per_day.get(day)
        if s is None:
            s = set()
            seen_per_day[day] = s

        key = _dedup_key(rec)
        if key in s:
            return
        s.add(key)

        if len(arr) < per_day:
            arr.append(rec)

    if mode in ("json","hybrid"):
        try:
            for r in store._MEM.values():
                if t and r.get("type") != t:
                    continue
                ts = int(r.get("ts") or 0)
                if ts < cutoff:
                    continue
                day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                rr = dict(r); rr["_src"]="json"; rr["_ts"]=ts
                rr = _maybe_strip_vectors(rr)
                put(day, rr)
        except Exception:
            pass

    if mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                lim = min(5000, max(500, days * per_day * 3))
                for r in ch.list_recent(type_filter=t, limit=lim):
                    ts = r.get("ts")
                    if ts is None:
                        continue
                    try:
                        ts = int(ts)
                    except Exception:
                        continue
                    if ts < cutoff:
                        continue
                    day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                    rr = dict(r); rr["_src"]="chroma"; rr["_ts"]=ts
                    rr = _maybe_strip_vectors(rr)
                    put(day, rr)
        except Exception:
            pass

    days_sorted = sorted(buckets.keys(), reverse=True)
    out = []
    for d in days_sorted:
        arr = buckets[d]
        try:
            arr.sort(key=lambda x: int(x.get("_ts") or 0), reverse=True)
        except Exception:
            pass
        out.append({"day": d, "count": len(arr), "items": arr[:per_day]})

    return jsonify({"ok": True, "backend": mode, "days": days, "per_day": per_day, "type": t, "buckets": out})

@bp.route("/add", methods=["POST"])
def add_():
    d = request.get_json(force=True, silent=True) or {}
    typ = d.get("type","fact")
    txt = d.get("text","")
    meta = d.get("meta")
    mode = _backend_mode()
    dual = _dual_write()

    rec_json = None
    rec_chroma = None

    try:
        rec_json = memory_add(typ, txt, meta)
    except Exception:
        rec_json = None

    if mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                if dual or mode == "chroma":
        except Exception:
            rec_chroma = None

    return jsonify({"ok": True, "backend": mode, "dual_write": dual, "record": {"json": rec_json, "chroma": rec_chroma}})

@bp.route("/forget", methods=["POST"])
def forget_():
    d = request.get_json(force=True, silent=True) or {}
    rid = (d.get("id","") or "").strip()
    src = (d.get("src","both") or "both").strip().lower()
    if src not in ("json","chroma","both"):
        src = "both"

    ok_json = False
    ok_chroma = False

    if rid and src in ("json","both"):
        try: ok_json = bool(store.forget(rid))
        except Exception: ok_json = False

    if rid and src in ("chroma","both") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                ok_chroma = bool(ch.delete(rid))
        except Exception:
            ok_chroma = False

    return jsonify({"ok": bool(ok_json or ok_chroma), "json": ok_json, "chroma": ok_chroma})

@bp.route("/snapshot", methods=["POST"])
def snapshot_():
    path = None
    try:
        store.snapshot()
        path = getattr(store, "_FILE", None)
    except Exception:
        pass

    chroma_status = None
    if get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if ch is not None:
                chroma_status = ch.status()
        except Exception:
            chroma_status = None

    return jsonify({"ok": True, "json_path": path, "chroma": chroma_status})

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_memory.html")

def register(app):
    app.register_blueprint(bp)
'''

write_text(CHROMA_ADAPTER, chroma_adapter_new)
write_text(MEMORY_ROUTES,  memory_routes_new)

# compile smoke + rollback
try:
    py_compile.compile(str(CHROMA_ADAPTER), doraise=True)
    py_compile.compile(str(MEMORY_ROUTES), doraise=True)
except Exception as e:
    shutil.copy2(str(b1), str(CHROMA_ADAPTER))
    shutil.copy2(str(b2), str(MEMORY_ROUTES))
    raise SystemExit(f"A2e failed, rolled back: {e}")

print("OK: ITER A2e applied")
print("  backups:", b1.name, b2.name)

# runtime smoke (non-fatal)
try:
    from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
    ch = get_chroma_ui()
    if ch is None:
        print("  smoke: chroma_ui=None (fallback ok)")
    else:
        st = ch.status()
        print("  smoke: chroma ok=", st.get("ok"), "total=", st.get("total_count"))
        if st.get("warnings"):
            print("  warnings:", st.get("warnings"))
except Exception as e:
    print("  smoke: chroma import failed (fallback ok). err=", e)

print("A2e done.")