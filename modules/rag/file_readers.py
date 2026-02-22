# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import io
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# ---- Konstanty/nastroyki (bezopasnye defolty)
TEXT_EXTS = {
    ".txt", ".md", ".rst", ".log", ".jsonl", ".cfg", ".ini",
    ".csv", ".tsv", ".yaml", ".yml"
}

ENV_KEYS_PATH = (
    "ESTER_RAG_FORCE_PATH",   # odnorazovyy fors s urovnya routera
    "RAG_DOCS_PATH",
    "ESTER_RAG_DOCS_DIR",
    "ESTER_RAG_DOCS_PATH",
    "ESTER_DOCS_DIR",
)

DEFAULT_SUBPATH = Path("~/.ester/docs")


# ---- Utility

def _as_str_env(name: str) -> str:
    """Vozvraschaet znachenie peremennoy okruzheniya kak stroku ('' esli net)."""
    v = os.getenv(name)
    return v if isinstance(v, str) else ""


def _expand_user_vars(p: str) -> str:
    """
    Korrektnoe rasshirenie ~ i %VARS%/$VARS (Windows/Linux).
    VAZhNO: zdes net Path.expandvars — ego v pathlib net; ispolzuem os.path.expandvars.
    """
    if not p:
        return ""
    return os.path.expanduser(os.path.expandvars(p))


def _coerce_path(val: str | Path) -> Path:
    """Privodim k Path s korrektnym expanduser/expandvars."""
    if isinstance(val, Path):
        s = str(val)
    else:
        s = val or ""
    s = _expand_user_vars(s)
    return Path(s)


def _ensure_text(s: str) -> str:
    try:
        return s if isinstance(s, str) else str(s)
    except Exception:
        return ""


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    return raw in ("1", "true", "yes", "y", "on")


def _iter_files(base: Path) -> Iterable[Path]:
    """Rekursivno obkhodim fayly s nuzhnymi rasshireniyami."""
    if not base.exists() or not base.is_dir():
        return []
    for p in base.rglob("*"):
        try:
            if p.is_file() and p.suffix.lower() in TEXT_EXTS:
                yield p
        except Exception:
            continue


def _read_text_file(p: Path, limit_bytes: int = 1_000_000) -> str:
    """
    Chtenie tekstovogo fayla v utf-8 s myagkoy degradatsiey.
    Dlya .jsonl berem kak est (line-based).
    """
    try:
        size = p.stat().st_size
        if size > limit_bytes:
            # Ogranichim chtenie bolshikh faylov
            with p.open("rb") as f:
                buf = f.read(limit_bytes)
            return buf.decode("utf-8", errors="replace")
        # Obychnoe chtenie
        with io.open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"[read_error:{e.__class__.__name__}] {e}"


# ---- Rezolving bazovoy direktorii

def _collect_candidates() -> Dict[str, str]:
    """Sobiraem kandidaty putey iz ENV (kak stroki bez ekspansii)."""
    return {k: _as_str_env(k) for k in ENV_KEYS_PATH}


def _pick_first_existing(paths: List[Path]) -> Optional[Path]:
    for p in paths:
        try:
            if p and p.exists() and p.is_dir():
                return p
        except Exception:
            continue
    return None


def _base_path() -> Optional[Path]:
    """
    Rezolvim bazovyy put k dokam:
    - prioritetno ESTER_RAG_FORCE_PATH (esli validen),
    - zatem pervyy suschestvuyuschiy iz ENV_KEYS_PATH,
    - inache defolt ~/.ester/docs (sozdaem pri neobkhodimosti).
    """
    # 1) fors
    forced = _as_str_env("ESTER_RAG_FORCE_PATH")
    if forced:
        p_forced = _coerce_path(forced)
        if p_forced.exists() and p_forced.is_dir():
            return p_forced

    # 2) kandidaty iz ENV
    candidates_raw = _collect_candidates()
    candidates_expanded = [
        _coerce_path(v) for k, v in candidates_raw.items() if v.strip()
    ]
    picked = _pick_first_existing(candidates_expanded)
    if picked:
        return picked

    # 3) defolt
    default_path = _coerce_path(DEFAULT_SUBPATH)
    try:
        default_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return default_path if default_path.exists() and default_path.is_dir() else None


# ---- Publichnye funktsii

def debug_status() -> Dict[str, object]:
    """Diagnostika bez padeniy."""
    cand = _collect_candidates()
    base = None
    try:
        base = _base_path()
    except Exception as e:
        # ne daem upast statusu
        base = None
        base_err = f"{e.__class__.__name__}: {e}"
    else:
        base_err = ""

    return {
        "rag_enabled": _bool_env("ESTER_RAG_ENABLE", False),
        "forced_path": _as_str_env("ESTER_RAG_FORCE_PATH"),
        "path_candidates": cand,
        "resolved_base": _ensure_text(base) if base else "",
        "resolved_exists": bool(base and Path(base).exists()),
        "error": base_err,
    }


def ingest_all(tag: str = "local_docs") -> Dict[str, object]:
    """
    Indeksatsiya vsekh tekstovykh faylov v bazovoy direktorii.
    Bezopasnaya: ne brosaet isklyucheniy naruzhu.
    """
    base = _base_path()
    if not base:
        return {"ok": False, "total": 0, "ingested": 0, "reason": "no_docs_path"}

    # Popytka podtyanut RAG-khab
    try:
        from modules.rag import hub  # type: ignore
    except Exception as e:
        return {
            "ok": False,
            "total": 0,
            "ingested": 0,
            "reason": f"no_rag_hub:{e.__class__.__name__}:{e}",
        }

    total = 0
    ingested = 0
    items: List[Dict[str, object]] = []

    # Skaniruem derevo
    for fp in _iter_files(base):
        total += 1
        txt = _read_text_file(fp)
        meta = {
            "path": str(fp),
            "name": fp.name,
            "ext": fp.suffix.lower(),
            "tag": tag,
        }
        items.append({"text": txt, "meta": meta})

    # Nichego ne nashli — eto ne oshibka, prosto pusto
    if not items:
        return {"ok": True, "total": 0, "ingested": 0, "empty": True, "base": str(base)}

    # Universalnaya myagkaya otpravka v hub
    ok = True
    reason = ""
    try:
        if hasattr(hub, "ingest_texts"):
            # ozhidaemyy variant: hub.ingest_texts(items, tag=?)
            res = hub.ingest_texts(items, tag=tag)  # type: ignore[attr-defined]
            # probuem vytaschit chislennost iz otveta
            if isinstance(res, dict) and "ingested" in res:
                ingested = int(res.get("ingested") or 0)
            else:
                ingested = len(items)
        elif hasattr(hub, "ingest"):
            res = hub.ingest(items=items, tag=tag)  # type: ignore[attr-defined]
            if isinstance(res, dict) and "ingested" in res:
                ingested = int(res.get("ingested") or 0)
            else:
                ingested = len(items)
        else:
            # Sovsem universalnaya degradatsiya: poshtuchno
            put_any = False
            for it in items:
                if hasattr(hub, "put"):
                    hub.put(it["text"], it.get("meta", {}), tag=tag)  # type: ignore[attr-defined]
                    put_any = True
                elif hasattr(hub, "add"):
                    hub.add(it["text"], it.get("meta", {}), tag=tag)  # type: ignore[attr-defined]
                    put_any = True
                else:
                    ok = False
                    reason = "hub_has_no_ingest_api"
                    break
                ingested += 1
            if not put_any and not reason:
                ok = False
                reason = "hub_no_supported_methods"
    except Exception as e:
        ok = False
        reason = f"hub_ingest_error:{e.__class__.__name__}:{e}"

    return {
        "ok": bool(ok and ingested >= 0),
        "total": total,
        "ingested": ingested,
        "base": str(base),
        "tag": tag,
        "reason": reason,
    }