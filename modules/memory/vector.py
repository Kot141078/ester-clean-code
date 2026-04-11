# -*- coding: utf-8 -*-
"""
modules/memory/vector.py — стабильная векторизация (fixed-dim) + cosine.

Проблема, которую лечим:
  старый embed мог выдавать вектора разной длины -> падение np.dot(shapes mismatch).

Решение:
  - fixed dim (по умолчанию 384, совместимо с all-MiniLM-L6-v2)
  - если sentence-transformers доступен — используем его, иначе безопасный hash-embed
  - cosine всегда работает (нормализация/нулевые вектора)

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
    # Дешёвый стабильный embed: складируем байты в фиксированные "корзины"
    b = (text or "").encode("utf-8", errors="ignore")
    v = np.zeros((dim,), dtype=np.float32)
    if not b:
        return v.tolist()
    for i, byte in enumerate(b):
        v[i % dim] += float(byte)
    # лёгкая нормализация масштаба
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
            # если вдруг модель не 384 — приводим к _DIM через folding
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
        # folding: сминаем любую длину в фиксированный dim (без падений)
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