# -*- coding: utf-8 -*-
from __future__ import annotations

"""routes_emotions.py — HTTP routes dlya emotsionalnogo dvizhka Ester.

Teper, kogda est polnotsennyy `emotional_engine.py`, routy mozhno sdelat prosche i pryamee:
- importiruem detect_emotions/top_emotions napryamuyu iz emotional_engine
- ostavlyaem best-effort fallback na sluchay “pereezda” API/oshibok importa (chtoby kontur ne padal)

Marshruty:
- GET  /emotions/ping    (bez JWT) — diagnostika, kakoy dvizhok podklyuchen
- POST /emotions/detect  (JWT)     — {text} -> {scores}
- POST /emotions/top     (JWT)     — {text,k} -> {top}

Mosty:
- Yavnyy: HTTP /emotions/* → emotional_engine → JSON.
- Skrytye:
  1) Kibernetika ↔ nadezhnost: fallback ne daet sisteme “umeret” iz-za odnogo importa.
  2) Infoteoriya ↔ ekonomiya: top-k + scores — korotkiy kanal obratnoy svyazi, ne taschim tekst obratno.

ZEMNOY ABZATs: v kontse fayla.
"""

from typing import Any, Dict, List, Tuple

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_ENGINE_KIND = "fallback"
_ENGINE_NOTE = "fallback-lexicon"


def _fallback_scores(text: str) -> Dict[str, float]:
    low = (text or "").lower()
    pos = ("ok", "good", "fine", "great", "happy", "thanks", "merci", "spasibo", "khorosho", "rad", "klass", "😍", "🙂", "😀")
    neg = ("bad", "sad", "angry", "error", "fail", "hate", "plokho", "ustal", "strash", "besit", "zlyus", "😡", "😢", "😭")
    score = 0
    for w in pos:
        if w in low:
            score += 1
    for w in neg:
        if w in low:
            score -= 1
    if score >= 2:
        return {"positive": 0.85, "neutral": 0.10, "negative": 0.05}
    if score <= -2:
        return {"negative": 0.85, "neutral": 0.10, "positive": 0.05}
    return {"neutral": 0.70, "positive": 0.15, "negative": 0.15}


# --- Prefer the real engine ---
try:
    from emotional_engine import detect_emotions as _detect_emotions  # type: ignore
    from emotional_engine import top_emotions as _top_emotions  # type: ignore

    _ENGINE_KIND = "emotional_engine"
    _ENGINE_NOTE = "detect_emotions/top_emotions"
except Exception as e:
    # best-effort: keep fallback
    _ENGINE_NOTE = f"import failed: {e}"


def detect_emotions(text: str) -> Dict[str, float]:
    if _ENGINE_KIND == "emotional_engine":
        try:
            res = _detect_emotions(text)  # type: ignore[name-defined]
            if isinstance(res, dict):
                return {str(k): float(v) for k, v in res.items()}
        except Exception:
            return _fallback_scores(text)
    return _fallback_scores(text)


def top_emotions(text: str, k: int = 3) -> List[Tuple[str, float]]:
    k = max(1, min(int(k or 3), 10))
    if _ENGINE_KIND == "emotional_engine":
        try:
            res = _top_emotions(text, k=k)  # type: ignore[name-defined]
            # ozhidaem spisok par
            if isinstance(res, list):
                out: List[Tuple[str, float]] = []
                for it in res:
                    if isinstance(it, (list, tuple)) and len(it) == 2:
                        out.append((str(it[0]), float(it[1])))
                if out:
                    return out[:k]
        except Exception:
            pass
    scores = detect_emotions(text)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]


def register_emotions_routes(app, memory_manager=None, url_prefix: str = "/emotions"):
    """Vozvraschaet Blueprint. Registriruy ego snaruzhi cherez app.register_blueprint(bp)."""
    bp = Blueprint("emotions", __name__)

    @bp.get(url_prefix + "/ping")
    def emotions_ping():
        return jsonify({"ok": True, "engine": _ENGINE_KIND, "note": _ENGINE_NOTE})

    @bp.post(url_prefix + "/detect")
    @jwt_required()
    def emotions_detect():
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        text = str(data.get("text") or "")
        scores = detect_emotions(text)

        # best-effort telemetry into memory
        try:
            if memory_manager is not None and hasattr(memory_manager, "add_record"):
                memory_manager.add_record(
                    f"[emotions] n={len(text)} scores={scores}",
                    tags=["telemetry", "emotions"],
                )  # type: ignore
        except Exception:
            pass

        return jsonify({"scores": scores, "engine": _ENGINE_KIND})

    @bp.post(url_prefix + "/top")
    @jwt_required()
    def emotions_top():
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        text = str(data.get("text") or "")
        k = int(data.get("k", 3))
        return jsonify({"top": top_emotions(text, k=k), "engine": _ENGINE_KIND})

    return bp


__all__ = ["register_emotions_routes"]


ZEMNOY = """
ZEMNOY ABZATs (anatomiya/inzheneriya):
Eto kak podklyuchit normalnyy “analiz krovi” vmesto test‑poloski.
Poloska (fallback) ostaetsya kak avariynyy variant, no v shtatnom rezhime my chitaem pokazateli iz nastoyaschey laboratorii —
i pri etom interfeys dlya vneshnego mira (routy) ostaetsya stabilnym.
"""