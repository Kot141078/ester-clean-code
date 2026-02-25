# -*- coding: utf-8 -*-
"""ITER A2b:
- modules/memory/chroma_adapter.py: robust list (peek/get fallback) + telemetry log silence
- routes/memory_routes.py: /memory/list vklyuchaet chroma, /memory/timeline addavlen
- tools/patches/chroma_locator.py: nakhodit realnye chroma.sqlite3 i pokazyvaet kollektsii/schetchiki
Smoke: compile + chroma status + locator run.

YaVNYY MOST: c=a+b - ne teryaem pamyat, a delaem ee vidimoy i prokhodimoy.
SKRYTYE MOSTY:
  - Ashby: dva khranilischa = variety, no s markirovkoy _src i rezhimami.
  - Cover&Thomas: limity vydachi i bakety taymlayna = kontrol kanala.
ZEMNOY ABZATs:
  Eto kak sklad + arkhiv: sklad (Chroma) bystryy, arkhiv (JSON) nadezhnyy. UI dolzhen videt both,
  i pri etom ne putat korobki (istochnik pomechaem)."""
from __future__ import annotations

import sys, time, shutil, py_compile
from pathlib import Path

ROOT = Path(r"D:\ester-project").resolve()
sys.path.insert(0, str(ROOT))

def backup(p: Path) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    b = p.with_suffix(p.suffix + f".bak_A2b_{ts}")
    shutil.copy2(str(p), str(b))
    return b

def write_text(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

CHROMA_ADAPTER = ROOT / "modules" / "memory" / "chroma_adapter.py"
MEMORY_ROUTES  = ROOT / "routes" / "memory_routes.py"
LOCATOR        = ROOT / "tools" / "patches" / "chroma_locator.py"

if not CHROMA_ADAPTER.exists():
    raise SystemExit(f"Missing: {CHROMA_ADAPTER}")
if not MEMORY_ROUTES.exists():
    raise SystemExit(f"Missing: {MEMORY_ROUTES}")

b1 = backup(CHROMA_ADAPTER)
b2 = backup(MEMORY_ROUTES)

chroma_adapter_new = r'''# -*- coding: utf-8 -*-
from __future__ import annotations

import os, time, uuid, logging
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

def _default_persist_dir() -> str:
    p = _env("CHROMA_PERSIST_DIR", "")
    if p: return p
    vroot = _env("ESTER_VSTORE_ROOT", "")
    if vroot: return os.path.join(vroot, "chroma")
    home = _env("ESTER_STATE_DIR", "") or _env("ESTER_HOME", "")
    if home: return os.path.join(home, "vstore", "chroma")
    return os.path.join(os.getcwd(), "vstore", "chroma")

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

class ChromaUI:
    def __init__(self) -> None:
        self.persist_dir = _default_persist_dir()
        self.collection_name = _env("CHROMA_COLLECTION_UI", "ester_global") or "ester_global"
        self.embed_model = _env("MEM_EMBED_MODEL", "all-MiniLM-L6-v2") or "all-MiniLM-L6-v2"
        self._ok = False
        self._err = ""
        self.client = None
        self.coll = None
        if chromadb is None:
            self._err = "chromadb not installed"
            return
        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            ef = None
            if embedding_functions is not None:
                try:
                    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=self.embed_model)
                except Exception:
                    ef = None
            # Some versions don't like embedding_function=None explicitly
            try:
                if ef is not None:
                    self.coll = self.client.get_or_create_collection(name=self.collection_name, embedding_function=ef)
                else:
                    self.coll = self.client.get_or_create_collection(name=self.collection_name)
            except TypeError:
                self.coll = self.client.get_or_create_collection(name=self.collection_name)
            self._ok = True
        except Exception as e:
            self._ok = False
            self._err = str(e)

    def available(self) -> bool:
        return bool(self._ok and self.coll is not None)

    def status(self) -> Dict[str, Any]:
        out = {
            "ok": self.available(),
            "persist_dir": self.persist_dir,
            "collection": self.collection_name,
            "embed_model": self.embed_model,
            "error": self._err,
        }
        if self.available():
            try: out["count"] = int(self.coll.count())
            except Exception: out["count"] = None
        return out

    def add_record(self, type_: str, text: str, meta: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if not self.available(): return None
        t = (text or "").strip()
        if not t: return None
        m = dict(meta or {})
        typ = (type_ or m.get("type") or "fact")
        now = int(time.time())
        m.setdefault("type", typ)
        m.setdefault("time", now)
        _id = f"ui_{uuid.uuid4().hex}"
        try:
            self.coll.add(documents=[t], metadatas=[m], ids=[_id])
        except Exception:
            return None
        return {"id": _id, "type": typ, "text": t, "meta": m, "ts": now}

    def delete(self, rid: str) -> bool:
        if not self.available(): return False
        rid = (rid or "").strip()
        if not rid: return False
        try:
            self.coll.delete(ids=[rid])
            return True
        except Exception:
            return False

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.available(): return []
        q = (query or "").strip()
        if not q: return []
        k = max(1, int(top_k or 5))
        try:
            res = self.coll.query(
                query_texts=[q],
                n_results=k,
                include=["documents", "metadatas", "distances", "ids"],
            )
        except Exception:
            return []
        ids = (res.get("ids") or [[]])[0] or []
        docs = (res.get("documents") or [[]])[0] or []
        metas = (res.get("metadatas") or [[]])[0] or []
        dists = (res.get("distances") or [[]])[0] or []
        out: List[Dict[str, Any]] = []
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
            })
        # recent first if possible
        try:
            out.sort(key=lambda r: int(r.get("ts") or 0), reverse=True)
        except Exception:
            pass
        return out

    def list_recent(self, type_filter: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Robust listing for different Chroma versions:
        1) try coll.peek(limit)
        2) try coll.get(where=..., include=..., limit=...)
        3) try coll.get(where=..., include=...) then slice
        Sort by meta.time desc if present.
        """
        if not self.available(): return []
        lim = max(1, min(5000, int(limit or 200)))

        ids: List[str] = []
        docs: List[str] = []
        metas: List[Any] = []

        # 1) peek
        res = None
        try:
            res = self.coll.peek(limit=lim)
        except TypeError:
            try:
                res = self.coll.peek(lim)
            except Exception:
                res = None
        except Exception:
            res = None

        if isinstance(res, dict) and res.get("ids") is not None:
            ids = res.get("ids") or []
            docs = res.get("documents") or []
            metas = res.get("metadatas") or []
        else:
            # 2) get with where/limit
            where = {"type": str(type_filter)} if type_filter else None
            try:
                res = self.coll.get(include=["documents", "metadatas", "ids"], where=where, limit=lim)
            except TypeError:
                try:
                    res = self.coll.get(include=["documents", "metadatas", "ids"], where=where)
                except Exception:
                    res = None
            except Exception:
                res = None

            if isinstance(res, dict):
                ids = res.get("ids") or []
                docs = res.get("documents") or []
                metas = res.get("metadatas") or []

        out: List[Dict[str, Any]] = []
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
            })

        try:
            out.sort(key=lambda r: int(r.get("ts") or 0), reverse=True)
        except Exception:
            pass
        return out[:lim]


_UI_SINGLETON: Optional[ChromaUI] = None
def get_chroma_ui() -> Optional[ChromaUI]:
    global _UI_SINGLETON
    if _UI_SINGLETON is None:
        try:
            _UI_SINGLETON = ChromaUI()
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
    ok = bool(ch is not None and getattr(ch, "available", lambda: False)())
    if not ok:
        return "json"
    if mode == "chroma":
        return "chroma"
    if mode == "hybrid":
        return "hybrid"
    return "hybrid"  # auto

def _dual_write() -> bool:
    v = (os.getenv("MEM_UI_DUAL_WRITE", "1") or "1").strip().lower()
    return v not in ("0","false","no","off")

def _dedup(items):
    seen = set()
    out = []
    for r in items:
        key = (str(r.get("type") or ""), (r.get("text") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

@bp.route("/list", methods=["GET"])
def list_():
    t = request.args.get("type")
    limit = int((request.args.get("limit","200") or "200").strip() or 200)
    limit = max(1, min(1000, limit))
    mode = _backend_mode()

    items = []

    # 1) chroma first (if available) — to show “zhivuyu” pamyat
    if mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                for r in ch.list_recent(type_filter=t, limit=limit):
                    rr = dict(r); rr["_src"]="chroma"; items.append(rr)
        except Exception:
            pass

    # 2) json
    if mode in ("json","hybrid"):
        data = [r for r in store._MEM.values() if (not t or r.get("type") == t)]
        try:
            data.sort(key=lambda x: int(x.get("ts",0) or 0), reverse=True)
        except Exception:
            pass
        data = data[:limit]
        for r in data:
            rr = dict(r); rr["_src"]="json"; items.append(rr)

    if mode == "hybrid":
        items = _dedup(items)

    return jsonify({"ok": True, "backend": mode, "count": len(items), "items": items})

@bp.route("/search", methods=["GET"])
def search_():
    q = (request.args.get("q","") or "").strip()
    k = int((request.args.get("k","5") or "5").strip() or 5)
    k = max(1, min(20, k))
    mode = _backend_mode()
    results = []

    if q and mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                for r in ch.search(q, top_k=k):
                    rr = dict(r); rr["_src"]="chroma"; results.append(rr)
        except Exception:
            pass

    if q and mode in ("json","hybrid"):
        try:
            for r in store.query(q, top_k=k):
                rr = dict(r); rr["_src"]="json"; results.append(rr)
        except Exception:
            pass

    if mode == "hybrid":
        results = _dedup(results)

    return jsonify({"ok": True, "backend": mode, "query": q, "results": results})

@bp.route("/timeline", methods=["GET"])
def timeline_():
    days = int((request.args.get("days","30") or "30").strip() or 30)
    per_day = int((request.args.get("per_day","20") or "20").strip() or 20)
    t = request.args.get("type")
    src = (request.args.get("src","auto") or "auto").strip().lower()
    if src not in ("auto","json","chroma","hybrid"):
        src = "auto"

    mode = _backend_mode()
    # if the user asked for src explicitly, we respect it
    if src != "auto":
        mode = src

    days = max(1, min(365, days))
    per_day = max(1, min(200, per_day))
    now = int(time.time())
    cutoff = now - days * 86400

    buckets = {}  # day -> list
    def put(day: str, rec: dict):
        arr = buckets.get(day)
        if arr is None:
            arr = []
            buckets[day] = arr
        if len(arr) < per_day:
            arr.append(rec)

    # JSON
    if mode in ("json","hybrid"):
        try:
            for r in store._MEM.values():
                if t and r.get("type") != t:
                    continue
                ts = int(r.get("ts") or 0)
                if ts < cutoff:
                    continue
                day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                rr = dict(r)
                rr["_src"] = "json"
                rr["_ts"] = ts
                put(day, rr)
        except Exception:
            pass

    # Chroma
    if mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                # berem "s zapasom" — potom otfiltruem po cutoff
                lim = min(5000, max(500, days * per_day))
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
                    rr = dict(r)
                    rr["_src"] = "chroma"
                    rr["_ts"] = ts
                    put(day, rr)
        except Exception:
            pass

    # finalnaya sortirovka dney
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

    # JSON — vsegda (nadezhnyy zhurnal)
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

locator_new = r'''# -*- coding: utf-8 -*-
from __future__ import annotations

import os, sys
from pathlib import Path

ROOT = Path(r"D:\ester-project").resolve()
sys.path.insert(0, str(ROOT))

try:
    import chromadb  # type: ignore
    from chromadb.config import Settings  # type: ignore
except Exception:
    chromadb = None  # type: ignore
    Settings = None  # type: ignore

def _cands():
    out = []
    out.append(ROOT)
    for env in ("CHROMA_PERSIST_DIR","ESTER_VSTORE_ROOT","ESTER_HOME","ESTER_STATE_DIR"):
        v = (os.getenv(env,"") or "").strip()
        if v:
            out.append(Path(v))
            out.append(Path(v) / "chroma")
            out.append(Path(v) / "vstore" / "chroma")
    # tipichnye
    out.append(ROOT / "vstore" / "chroma")
    out.append(ROOT / "data" / "vstore" / "chroma")
    # uniq existing dirs
    uniq = []
    seen = set()
    for p in out:
        try:
            p = p.resolve()
        except Exception:
            continue
        if p.exists() and p.is_dir() and str(p) not in seen:
            uniq.append(p); seen.add(str(p))
    return uniq

def _find_sqlite(roots):
    hits = []
    for r in roots:
        try:
            for p in r.rglob("chroma.sqlite3"):
                hits.append(p.parent)
        except Exception:
            pass
    # uniq
    uniq = []
    seen = set()
    for h in hits:
        h = h.resolve()
        if str(h) not in seen:
            uniq.append(h); seen.add(str(h))
    return uniq

def main():
    roots = _cands()
    dirs = _find_sqlite(roots)
    print("CHROMA LOCATOR")
    if chromadb is None:
        print("chromadb not installed -> cannot inspect collections")
        for d in dirs:
            print(" -", d)
        return

    if not dirs:
        print("No chroma.sqlite3 found under candidates.")
        return

    for d in dirs[:20]:
        print("\nDIR:", d)
        try:
            client = chromadb.PersistentClient(path=str(d), settings=Settings(anonymized_telemetry=False))
            cols = client.list_collections()
            if not cols:
                print("  collections: []")
                continue
            for c in cols:
                try:
                    name = getattr(c, "name", None) or str(c)
                    coll = client.get_collection(name=name)
                    cnt = coll.count()
                    print("  -", name, "count=", cnt)
                except Exception as e:
                    print("  -", getattr(c, "name", str(c)), "err=", e)
        except Exception as e:
            print("  open err:", e)

if __name__ == "__main__":
    main()
'''

write_text(CHROMA_ADAPTER, chroma_adapter_new)
write_text(MEMORY_ROUTES,  memory_routes_new)
write_text(LOCATOR,        locator_new)

# compile smoke + rollback
try:
    py_compile.compile(str(CHROMA_ADAPTER), doraise=True)
    py_compile.compile(str(MEMORY_ROUTES), doraise=True)
    py_compile.compile(str(LOCATOR), doraise=True)
except Exception as e:
    shutil.copy2(str(b1), str(CHROMA_ADAPTER))
    shutil.copy2(str(b2), str(MEMORY_ROUTES))
    raise SystemExit(f"A2b failed, rolled back: {e}")

print("OK: ITER A2b applied")
print("  backups:", b1.name, b2.name)

# runtime smoke
try:
    from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
    ch = get_chroma_ui()
    if ch is None:
        print("  smoke: chroma_ui=None (fallback ok)")
    else:
        st = ch.status()
        print("  smoke: chroma ok=", st.get("ok"), "dir=", st.get("persist_dir"), "coll=", st.get("collection"), "count=", st.get("count"))
        if st.get("ok"):
            lst = ch.list_recent(limit=3)
            print("  smoke: chroma list_recent sample=", len(lst))
except Exception as e:
    print("  smoke: chroma import failed (fallback ok). err=", e)

print("\n--- running locator ---")
try:
    import runpy
    runpy.run_path(str(LOCATOR), run_name="__main__")
except Exception as e:
    print("locator failed:", e)

print("\nA2b done.")