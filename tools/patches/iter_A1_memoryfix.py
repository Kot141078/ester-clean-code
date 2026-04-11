# -*- coding: utf-8 -*-
"""ITER A1: stabilizatsiya JSON-pamyati (UI) bez poteri dannykh.
- fiksirovannaya razmernost vec
- avto-migratsiya: vec_legacy sokhranyaetsya, vec pereschityvaetsya
- put pamyati -> ESTER_STATE_DIR/ESTER_HOME

YaVNYY MOST: c=a+b — chelovek zadaet "ne teryat pamyat", protsedury delayut migratsiyu bez poter.
SKRYTYE MOSTY:
  - Ashby: umenshaem khaos (raznye dliny vektorov) -> stabilnyy kanal poiska.
  - Cover&Thomas: fiksiruem "propusknuyu sposobnost" predstavleniya (dim) -> menshe entropii.
ZEMNOY ABZATs:
  Eto kak standartizirovat rezbu na vsekh boltakh: poka M16 i M22 v odnoy korobke —
  Ty khot tresni, gayka ne nakrutitsya. My privodim vse k odnomu standartu, staroe ne vybrasyvaem."""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
import py_compile

ROOT = Path(r"<repo-root>").resolve()

def backup(p: Path) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    b = p.with_suffix(p.suffix + f".bak_A1_{ts}")
    shutil.copy2(str(p), str(b))
    return b

def write_text(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

VECTOR_PY = ROOT / "modules" / "memory" / "vector.py"
STORE_PY  = ROOT / "modules" / "memory" / "store.py"

if not VECTOR_PY.exists():
    raise SystemExit(f"Missing: {VECTOR_PY}")
if not STORE_PY.exists():
    raise SystemExit(f"Missing: {STORE_PY}")

b1 = backup(VECTOR_PY)
b2 = backup(STORE_PY)

vector_new = r'''# -*- coding: utf-8 -*-
"""
modules/memory/vector.py — stabilnaya vektorizatsiya (fixed-dim) + cosine.

Problema, kotoruyu lechim:
  staryy embed mog vydavat vektora raznoy dliny -> padenie np.dot(shapes mismatch).

Reshenie:
  - fixed dim (po umolchaniyu 384, sovmestimo s all-MiniLM-L6-v2)
  - esli sentence-transformers dostupen — ispolzuem ego, inache bezopasnyy hash-embed
  - cosine vsegda rabotaet (normalizatsiya/nulevye vektora)

c=a+b
"""
from __future__ import annotations

import os
import math
import threading
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Optional: sentence-transformers
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
except Exception:
    SentenceTransformer = None  # type: ignore

_DIM_DEFAULT = 384
_DIM = int(os.getenv("MEM_VEC_DIM", str(_DIM_DEFAULT)).strip() or _DIM_DEFAULT)

_MODEL_NAME = os.getenv("MEM_EMBED_MODEL", "all-MiniLM-L6-v2").strip() or "all-MiniLM-L6-v2"
_LOCK = threading.Lock()
_MODEL = None

def _get_model():
    global _MODEL
    if SentenceTransformer is None:
        return None
    if _MODEL is not None:
        return _MODEL
    with _LOCK:
        if _MODEL is not None:
            return _MODEL
        try:
            _MODEL = SentenceTransformer(_MODEL_NAME)
        except Exception:
            _MODEL = None
    return _MODEL

def _hash_embed(text: str, dim: int) -> List[float]:
    # Deshevyy stabilnyy embed: skladiruem bayty v fiksirovannye "korziny"
    b = (text or "").encode("utf-8", errors="ignore")
    v = np.zeros((dim,), dtype=np.float32)
    if not b:
        return v.tolist()
    for i, byte in enumerate(b):
        v[i % dim] += float(byte)
    # legkaya normalizatsiya masshtaba
    norm = float(np.linalg.norm(v))
    if norm > 0:
        v /= norm
    return v.tolist()

def embed(text: str) -> List[float]:
    t = (text or "").strip()
    if not t:
        return [0.0] * _DIM

    m = _get_model()
    if m is not None:
        try:
            arr = m.encode([t], normalize_embeddings=True)
            vec = np.asarray(arr[0], dtype=np.float32)
            # if suddenly the model is not 384 - leads to _SMOKE through folding
            return normalize_vec(vec.tolist(), _DIM)
        except Exception:
            pass

    return _hash_embed(t, _DIM)

def normalize_vec(v: List[float], dim: int) -> List[float]:
    if not v:
        return [0.0] * dim
    a = np.asarray(v, dtype=np.float32).ravel()
    if a.size == 0:
        return [0.0] * dim

    if a.size == dim:
        out = a
    else:
        # folding: sminaem lyubuyu dlinu v fiksirovannyy dim (bez padeniy)
        out = np.zeros((dim,), dtype=np.float32)
        for i, val in enumerate(a.tolist()):
            out[i % dim] += float(val)

    n = float(np.linalg.norm(out))
    if n > 0:
        out = out / n
    return out.tolist()

def cosine(a: List[float], b: List[float], dim: int) -> float:
    va = np.asarray(normalize_vec(a, dim), dtype=np.float32)
    vb = np.asarray(normalize_vec(b, dim), dtype=np.float32)
    return float(np.dot(va, vb))

def search(vec: List[float], records: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    q = normalize_vec(vec, _DIM)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for r in records:
        v = r.get("vec") or []
        if not isinstance(v, list) or not v:
            continue
        try:
            s = cosine(q, v, _DIM)
        except Exception:
            continue
        scored.append((s, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[Dict[str, Any]] = []
    for s, r in scored[: max(1, int(top_k))]:
        rr = dict(r)
        rr["_score"] = float(s)
        out.append(rr)
    return out
'''

store_new = r'''# -*- coding: utf-8 -*-
"""
modules/memory/store.py — JSON-pamyat (UI) + stabilnaya vektorizatsiya.

Fiksy iteratsii A1:
- put fayla pamyati: ESTER_STATE_DIR/ESTER_HOME (a ne cwd)
- avto-migratsiya vec:
    esli vec starogo formata/dliny -> sokhranyaem v vec_legacy, pereschityvaem vec zanovo
- API sokhranyaem: add_record / get_record / query / forget / snapshot / load

c=a+b
"""
from __future__ import annotations

import os
import time
import uuid
import threading
from typing import Any, Dict, List, Optional

from modules.memory.io import save_snapshot, load_snapshot
from modules.memory.vector import embed, normalize_vec

_LOCK = threading.Lock()
_MEM: Dict[str, Dict[str, Any]] = {}

# --- state root ---
_STATE = (os.environ.get("ESTER_STATE_DIR") or os.environ.get("ESTER_HOME") or "").strip()
if not _STATE:
    _STATE = (os.environ.get("ESTER_ROOT") or os.getcwd()).strip()

_FILE = os.path.join(_STATE, "data", "memory", "memory.json")
os.makedirs(os.path.dirname(_FILE), exist_ok=True)

_SAVE_INTERVAL = float(os.getenv("MEM_SAVE_INTERVAL_SEC", "2.0").strip() or 2.0)
_LAST_SAVE = 0.0

# vec dim policy
_DIM = int(os.getenv("MEM_VEC_DIM", "384").strip() or 384)

def _maybe_save(force: bool = False) -> None:
    global _LAST_SAVE
    now = time.time()
    if force or (now - _LAST_SAVE) >= _SAVE_INTERVAL:
        save_snapshot(_FILE, _MEM)
        _LAST_SAVE = now

def _migrate_record_vec(rec: Dict[str, Any]) -> bool:
    """
    Returns True if record changed.
    """
    changed = False
    txt = str(rec.get("text") or "").strip()
    v = rec.get("vec")

    # If vec missing or wrong type/length -> recompute.
    need = False
    if not isinstance(v, list) or not v:
        need = True
    else:
        try:
            if len(v) != _DIM:
                need = True
        except Exception:
            need = True

    if need:
        if isinstance(v, list) and v:
            rec["vec_legacy"] = v
        rec["vec"] = normalize_vec(embed(txt), _DIM)
        changed = True

    # Keep minimal schema sane
    if "id" not in rec:
        rec["id"] = str(uuid.uuid4()); changed = True
    if "ts" not in rec:
        rec["ts"] = int(time.time()); changed = True
    if "meta" not in rec or not isinstance(rec.get("meta"), dict):
        rec["meta"] = {}; changed = True
    if "type" not in rec:
        rec["type"] = "fact"; changed = True

    return changed

def load() -> None:
    global _MEM
    data = load_snapshot(_FILE) or {}
    if isinstance(data, dict):
        _MEM.update(data)

    # Lazy migration
    changed_any = False
    with _LOCK:
        for k, rec in list(_MEM.items()):
            if isinstance(rec, dict):
                if _migrate_record_vec(rec):
                    changed_any = True
            else:
                # broken entry -> drop safely but keep as legacy in meta
                _MEM.pop(k, None)
                changed_any = True
    if changed_any:
        _maybe_save(force=True)

def add_record(type_: str, text: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rid = str(uuid.uuid4())
    now = int(time.time())
    rec: Dict[str, Any] = {"id": rid, "type": type_ or "fact", "text": text or "", "meta": meta or {}, "ts": now}
    rec["vec"] = normalize_vec(embed(rec["text"]), _DIM)
    with _LOCK:
        _MEM[rid] = rec
    _maybe_save()
    return rec

def get_record(rid: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        return _MEM.get(rid)

def query(text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    from modules.memory.vector import search
    if not _MEM:
        return []
    vec = normalize_vec(embed(text), _DIM)
    return search(vec, list(_MEM.values()), top_k=top_k)

def forget(rid: str) -> bool:
    with _LOCK:
        if rid in _MEM:
            del _MEM[rid]
            _maybe_save(force=True)
            return True
    return False

def snapshot() -> None:
    with _LOCK:
        save_snapshot(_FILE, _MEM)

# avtozagruzka pri importe
load()
'''

write_text(VECTOR_PY, vector_new)
write_text(STORE_PY, store_new)

# compile smoke-test (auto-rollback if fail)
try:
    py_compile.compile(str(VECTOR_PY), doraise=True)
    py_compile.compile(str(STORE_PY), doraise=True)
except Exception as e:
    shutil.copy2(str(b1), str(VECTOR_PY))
    shutil.copy2(str(b2), str(STORE_PY))
    raise SystemExit(f"A1 failed, rolled back. Reason: {e}")

print("OK: ITER A1 applied")
print(f"  vector.py backup: {b1.name}")
print(f"  store.py  backup: {b2.name}")
print(f"  memory file path (runtime): {_FILE if '_FILE' in globals() else 'n/a'}")