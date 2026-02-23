# -*- coding: utf-8 -*-
"""
ITER A2: routes/memory_routes.py -> hybrid JSON+Chroma (ester_global)
Sozdaet modules/memory/chroma_adapter.py i zamenyaet routes/memory_routes.py.
V kontse: compile smoke + bystryy runtime smoke (ne fatalnyy).
"""
from __future__ import annotations

import sys, time, shutil
from pathlib import Path
import py_compile

ROOT = Path(r"D:\ester-project").resolve()
sys.path.insert(0, str(ROOT))

def backup(p: Path) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    b = p.with_suffix(p.suffix + f".bak_A2_{ts}")
    shutil.copy2(str(p), str(b))
    return b

def write_text(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

CHROMA_ADAPTER_PY = ROOT / "modules" / "memory" / "chroma_adapter.py"
MEMORY_ROUTES_PY  = ROOT / "routes" / "memory_routes.py"

if not MEMORY_ROUTES_PY.exists():
    raise SystemExit(f"Missing: {MEMORY_ROUTES_PY}")

b_routes = backup(MEMORY_ROUTES_PY)
b_adapter = backup(CHROMA_ADAPTER_PY) if CHROMA_ADAPTER_PY.exists() else None

chroma_adapter_new = r'''# -*- coding: utf-8 -*-
from __future__ import annotations
import os, time, uuid
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

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
            self.coll = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=ef if ef is not None else None,
            )
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
        out = []
        for i in range(min(len(ids), len(docs))):
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else None
            ts = None
            typ = ""
            try:
                if isinstance(meta, dict):
                    typ = str(meta.get("type") or "")
                    ts = meta.get("time") or meta.get("ts")
            except Exception:
                pass
            out.append({
                "id": ids[i],
                "type": typ or "fact",
                "text": docs[i],
                "meta": meta if isinstance(meta, dict) else {},
                "ts": int(ts) if ts is not None else None,
                "_score": _score_from_distance(dist),
            })
        return out

_UI_SINGLETON: Optional[ChromaUI] = None
def get_chroma_ui() -> Optional[ChromaUI]:
    global _UI_SINGLETON
    if _UI_SINGLETON is None:
        try: _UI_SINGLETON = ChromaUI()
        except Exception: _UI_SINGLETON = None
    return _UI_SINGLETON
'''

memory_routes_new = r'''# -*- coding: utf-8 -*-
from __future__ import annotations

import os
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

@bp.route("/list", methods=["GET"])
def list_():
    t = request.args.get("type")
    limit = int((request.args.get("limit","200") or "200").strip() or 200)
    limit = max(1, min(1000, limit))
    mode = _backend_mode()
    items = []
    if mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                # prostaya vydacha: poslednie N cherez poisk po pustomu zaprosu ne delaem
                # vmesto etogo UI polzuetsya /search; /list v chroma mozhno dobavit pozzhe
                pass
        except Exception:
            pass
    if mode in ("json","hybrid"):
        data = [r for r in store._MEM.values() if (not t or r.get("type") == t)]
        try: data.sort(key=lambda x: int(x.get("ts",0) or 0), reverse=True)
        except Exception: pass
        data = data[:limit]
        for r in data:
            rr = dict(r); rr["_src"]="json"; items.append(rr)
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
    return jsonify({"ok": True, "backend": mode, "query": q, "results": results})

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
                if dual or mode=="chroma":
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

write_text(CHROMA_ADAPTER_PY, chroma_adapter_new)
write_text(MEMORY_ROUTES_PY,  memory_routes_new)

# compile smoke + rollback
try:
    py_compile.compile(str(CHROMA_ADAPTER_PY), doraise=True)
    py_compile.compile(str(MEMORY_ROUTES_PY), doraise=True)
except Exception as e:
    shutil.copy2(str(b_routes), str(MEMORY_ROUTES_PY))
    if b_adapter is not None:
        shutil.copy2(str(b_adapter), str(CHROMA_ADAPTER_PY))
    raise SystemExit(f"A2 failed, rolled back: {e}")

print("OK: ITER A2 applied")
print("  backup routes:", b_routes.name)
if b_adapter is not None:
    print("  backup adapter:", b_adapter.name)

# runtime smoke (non-fatal)
try:
    from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
    ch = get_chroma_ui()
    if ch is None:
        print("  smoke: chroma_ui=None (fallback to json)")
    else:
        st = ch.status()
        print("  smoke: chroma ok=", st.get("ok"), "dir=", st.get("persist_dir"), "coll=", st.get("collection"), "count=", st.get("count"))
except Exception as e:
    print("  smoke: chroma import failed (fallback ok). err=", e)

print("A2 done.")