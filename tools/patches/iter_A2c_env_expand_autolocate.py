# -*- coding: utf-8 -*-
"""ITER A2c: stop %VAR% path poisoning + auto-locate real Chroma store for UI.

YaVNYY MOST: c=a+b — ne teryaem pamyat i prekraschaem ee fragmentatsiyu iz-za putey.
SKRYTYE MOSTY:
  - Ashby: umenshaem khaos (odni i te zhe suschnosti pamyati v raznykh kornyakh) -> bolshe upravlyaemosti.
  - Cover&Thomas: avto-lokator vybiraet “samyy informativnyy” kanal (where count vyshe), ne peregruzhaya UI.
ZEMNOY ABZATs:
  Eto kak perestat podpisyvat korobki “%SKLAD%” i nachat pisat realnyy address.
  Poka adres ne razvernut - gruz uezzhaet v sluchaynyy garazh."""
from __future__ import annotations

import os, re, sys, time, shutil, py_compile
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = Path(r"D:\ester-project").resolve()
sys.path.insert(0, str(ROOT))

def backup(p: Path, tag: str) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    b = p.with_suffix(p.suffix + f".bak_{tag}_{ts}")
    shutil.copy2(str(p), str(b))
    return b

def write_text(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def replace_once(path: Path, old: str, new: str) -> None:
    s = path.read_text(encoding="utf-8", errors="ignore")
    if old not in s:
        raise SystemExit(f"Pattern not found in {path.name}: {old[:60]}...")
    s2 = s.replace(old, new, 1)
    path.write_text(s2, encoding="utf-8")

def re_sub_once(path: Path, pattern: str, repl: str, flags=0) -> None:
    s = path.read_text(encoding="utf-8", errors="ignore")
    s2, n = re.subn(pattern, repl, s, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f"Regex patch failed in {path.name} (matches={n}). pattern={pattern[:60]}...")
    path.write_text(s2, encoding="utf-8")

APP_PY = ROOT / "app.py"
RUN_PY = ROOT / "run_ester_fixed.py"
CHROMA_ADAPTER = ROOT / "modules" / "memory" / "chroma_adapter.py"

for p in (APP_PY, RUN_PY, CHROMA_ADAPTER):
    if not p.exists():
        raise SystemExit(f"Missing: {p}")

b_app = backup(APP_PY, "A2c")
b_run = backup(RUN_PY, "A2c")
b_chr = backup(CHROMA_ADAPTER, "A2c")

# --- 1) app.py: expandvars for ESTER_STATE_DIR ---
# old:
# STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
# new: expandvars + guard against unresolved %VAR%
app_old = 'STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()'
app_new = (
'def _safe_expand_path(v: str) -> str:\n'
'    v = (v or "").strip()\n'
'    if not v:\n'
'        return ""\n'
'    v2 = os.path.expandvars(os.path.expanduser(v))\n'
'    # unresolved %VAR% -> empty\n'
'    if re.search(r"%[A-Za-z_][A-Za-z0-9_]*%", v2):\n'
'        return ""\n'
'    return v2\n\n'
'raw_state = os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))\n'
'raw_state = _safe_expand_path(raw_state) or str(Path.home() / ".ester")\n'
'STATE_DIR = Path(raw_state).expanduser()\n'
)
# insert imports if needed: app.py already imports os/json/etc earlier; but we used re -> ensure re imported.
# safest: if "import re" missing, add it near top.
app_text = APP_PY.read_text(encoding="utf-8", errors="ignore")
if "\nimport re\n" not in app_text and "\nimport re\r\n" not in app_text:
    # add after "import os"
    re_sub_once(APP_PY, r"\nimport os\n", "\nimport os\nimport re\n", flags=0)

replace_once(APP_PY, app_old, app_new)

# --- 2) run_ester_fixed.py: harden _resolve_ester_home() to ignore poisoned values like '%ESTER_HOME%' ---
# Replace whole function block (keep name/signature)
func_pat = r"def _resolve_ester_home\(\) -> str:\n(?:[ \t]*#.*\n)?(?:[ \t].*\n)+?\s*return str\(Path\(h\)\.resolve\(\)\)\n"
run_repl = (
"def _resolve_ester_home() -> str:\n"
"    \"\"\"Resolve ESTER_HOME safely.\n"
"    If env value contains unresolved %VAR% (common with dotenv) -> ignore and fallback.\n"
"    \"\"\"\n"
"    def _looks_unexpanded(x: str) -> bool:\n"
"        try:\n"
"            return bool(re.search(r\"%[A-Za-z_][A-Za-z0-9_]*%\", x or \"\")) or (\"${\" in (x or \"\"))\n"
"        except Exception:\n"
"            return False\n"
"\n"
"    env_home = (os.environ.get(\"ESTER_HOME\") or \"\").strip()\n"
"    if env_home:\n"
"        h = os.path.expandvars(os.path.expanduser(env_home))\n"
"        # if still unexpanded -> ignore\n"
"        if not _looks_unexpanded(h):\n"
"            try:\n"
"                return str(Path(h).resolve())\n"
"            except Exception:\n"
"                return h\n"
"\n"
"    # fallback to user home\n"
"    try:\n"
"        h = str(Path.home() / \".ester\")\n"
"    except Exception:\n"
"        h = os.path.join(os.getcwd(), \".ester\")\n"
"    h = os.path.expandvars(os.path.expanduser(h))\n"
"    try:\n"
"        return str(Path(h).resolve())\n"
"    except Exception:\n"
"        return h\n"
)
re_sub_once(RUN_PY, func_pat, run_repl, flags=re.S)

# --- 3) modules/memory/chroma_adapter.py: expandvars + auto-locate richest ester_global if current is empty ---
chroma_new = r'''# -*- coding: utf-8 -*-
from __future__ import annotations

import os, time, uuid, logging, re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    if _looks_unexpanded(p2):
        return ""
    return p2

def _default_persist_dir() -> str:
    # explicit override wins
    p = _expand_path(_env("CHROMA_PERSIST_DIR", ""))
    if p:
        return p

    vroot = _expand_path(_env("ESTER_VSTORE_ROOT", ""))
    if vroot:
        return os.path.join(vroot, "chroma")

    home = _expand_path(_env("ESTER_STATE_DIR", "")) or _expand_path(_env("ESTER_HOME", ""))
    if home:
        return os.path.join(home, "vstore", "chroma")

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

def _candidate_roots(project_root: Optional[str] = None) -> List[Path]:
    roots: List[Path] = []
    if project_root:
        roots.append(Path(project_root))
    roots.append(Path(os.getcwd()))

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

def _find_sqlite_dirs(roots: List[Path]) -> List[Path]:
    hits: List[Path] = []
    for r in roots:
        try:
            for p in r.rglob("chroma.sqlite3"):
                hits.append(p.parent)
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

def _probe_counts(persist_dir: str, want_collection: str) -> Tuple[int, int]:
    """
    returns (want_count, total_best_count)
    """
    if chromadb is None:
        return (0, 0)
    try:
        client = chromadb.PersistentClient(path=str(persist_dir), settings=Settings(anonymized_telemetry=False))
        cols = client.list_collections()
        want = 0
        best = 0
        for c in cols or []:
            name = getattr(c, "name", None) or str(c)
            try:
                coll = client.get_collection(name=name)
                cnt = int(coll.count())
            except Exception:
                cnt = 0
            if cnt > best:
                best = cnt
            if name == want_collection:
                want = cnt
        return (want, best)
    except Exception:
        return (0, 0)

class ChromaUI:
    def __init__(self) -> None:
        self.project_root = _expand_path(_env("ESTER_PROJECT_ROOT", "")) or os.getcwd()
        self.collection_name = _env("CHROMA_COLLECTION_UI", "ester_global") or "ester_global"
        self.embed_model = _env("MEM_EMBED_MODEL", "all-MiniLM-L6-v2") or "all-MiniLM-L6-v2"

        self.persist_dir = _default_persist_dir()
        self._ok = False
        self._err = ""
        self.client = None
        self.coll = None

        if chromadb is None:
            self._err = "chromadb not installed"
            return

        # auto-locate if current seems empty and no explicit CHROMA_PERSIST_DIR given
        auto_locate = (_env("CHROMA_AUTO_LOCATE", "1").lower() not in ("0","false","no","off"))
        explicit = bool(_expand_path(_env("CHROMA_PERSIST_DIR", "")))

        if auto_locate and not explicit:
            want_cnt, best_cnt = _probe_counts(self.persist_dir, self.collection_name)
            if want_cnt == 0 and best_cnt == 0:
                # try to find richer db nearby
                roots = _candidate_roots(self.project_root)
                dirs = _find_sqlite_dirs(roots)
                best_dir = None
                best_want = -1
                best_any = -1
                for d in dirs:
                    w, a = _probe_counts(str(d), self.collection_name)
                    if w > best_want or (w == best_want and a > best_any):
                        best_want, best_any = w, a
                        best_dir = str(d)
                if best_dir and best_dir != self.persist_dir:
                    self.persist_dir = best_dir

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
        try:
            out.sort(key=lambda r: int(r.get("ts") or 0), reverse=True)
        except Exception:
            pass
        return out

    def list_recent(self, type_filter: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
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
write_text(CHROMA_ADAPTER, chroma_new)

# --- compile smoke + rollback ---
try:
    py_compile.compile(str(APP_PY), doraise=True)
    py_compile.compile(str(RUN_PY), doraise=True)
    py_compile.compile(str(CHROMA_ADAPTER), doraise=True)
except Exception as e:
    shutil.copy2(str(b_app), str(APP_PY))
    shutil.copy2(str(b_run), str(RUN_PY))
    shutil.copy2(str(b_chr), str(CHROMA_ADAPTER))
    raise SystemExit(f"A2c failed, rolled back. Reason: {e}")

print("OK: ITER A2c applied")
print("  backups:")
print("   -", b_app.name)
print("   -", b_run.name)
print("   -", b_chr.name)

# --- runtime smoke (non-fatal) ---
try:
    from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
    ch = get_chroma_ui()
    if ch is None:
        print("  smoke: chroma_ui=None (fallback ok)")
    else:
        st = ch.status()
        print("  smoke: chroma ok=", st.get("ok"), "dir=", st.get("persist_dir"), "coll=", st.get("collection"), "count=", st.get("count"))
except Exception as e:
    print("  smoke: chroma import failed (fallback ok). err=", e)

print("A2c done.")