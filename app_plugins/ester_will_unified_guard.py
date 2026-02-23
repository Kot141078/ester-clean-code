# -*- coding: utf-8 -*-
from __future__ import annotations
import json, os, uuid
from typing import Any, Dict, List, Tuple
from flask import jsonify, request  # type: ignore
try:
    from modules.will import unified_guard_adapter as will_guard  # type: ignore
except Exception:  # pragma: no cover
    will_guard = None  # type: ignore
try:
    from modules.volition.volition_gate import VolitionContext, get_default_gate  # type: ignore
except Exception:  # pragma: no cover
    VolitionContext = None  # type: ignore
    get_default_gate = None  # type: ignore

_DEFAULT_SENSITIVE: Tuple[Tuple[str, List[str], int], ...] = (
    ("/replication", ["files"], 1),
    ("/backup", ["files"], 1),
    ("/ingest", ["files"], 1),
    ("/p2p", ["network"], 2),
    ("/computer_use", ["rpa_ui"], 2),
    ("/ops", ["files", "network"], 2),
)

def _ab_mode() -> str:
    v = os.getenv("ESTER_WILL_UNIFIED_AB", "A").strip().upper()
    return "B" if v == "B" else "A"

def _load_sensitive() -> Tuple[Tuple[str, List[str], int], ...]:
    raw = os.getenv("ESTER_WILL_HTTP_GUARD_PATHS") or ""
    raw = raw.strip()
    if not raw:
        return _DEFAULT_SENSITIVE
    out: List[Tuple[str, List[str], int]] = []
    for chunk in raw.split(","):
        part = chunk.strip()
        if not part:
            continue
        path, *rest = part.split(":")
        path = path.strip() or "/"
        scopes: List[str] = []
        min_level = 1
        if rest:
            scopes = [s for s in rest[0].split("+") if s]
        if len(rest) > 1:
            try:
                min_level = int(rest[1])
            except ValueError:
                min_level = 1
        out.append((path, scopes, min_level))
    return tuple(out) or _DEFAULT_SENSITIVE

def _match(path: str, table: Tuple[Tuple[str, List[str], int], ...]) -> Tuple[str, List[str], int]:
    for prefix, scopes, lvl in table:
        if path.startswith(prefix):
            return prefix, scopes, lvl
    return "", [], 0

def register(app):  # pragma: no cover
    sensitive = _load_sensitive()
    if will_guard is None:
        print("[ester-will-guard] unified_guard_adapter missing; plugin is inert")
        # keep plugin alive for volition journaling even if legacy guard is absent

    @app.before_request
    def _ester_will_http_guard():
        path = request.path or "/"
        if path in ("/health", "/", "/favicon.ico") or path.startswith("/static"):
            return None
        prefix, scopes, min_level = _match(path, sensitive)
        if not prefix:
            return None

        if VolitionContext is not None and get_default_gate is not None:
            gate = get_default_gate()
            req_id = str(request.headers.get("X-Request-ID") or ("http_" + uuid.uuid4().hex[:10]))
            v_dec = gate.decide(
                VolitionContext(
                    chain_id=req_id,
                    step="http_route",
                    actor="api",
                    intent=f"http:{path}",
                    route=path,
                    needs=list(scopes or []),
                    budgets={},
                    metadata={"method": request.method, "prefix": prefix},
                )
            )
            if v_dec.slot == "B" and not v_dec.allowed:
                return jsonify(
                    {
                        "ok": False,
                        "by": "volition_gate",
                        "reason_code": v_dec.reason_code,
                        "reason": v_dec.reason,
                        "slot": v_dec.slot,
                        "route": path,
                    }
                ), 403

        mode = _ab_mode()
        if mode == "A":
            return None
        if will_guard is None:
            return None
        dec = will_guard.decide(
            area=prefix,
            need=scopes or None,
            min_level=min_level or 1,
            strict=True,
        )
        if dec.ok:
            return None
        body: Dict[str, Any] = {
            "ok": False,
            "by": "ester_will_unified_guard",
            "reason": dec.reason,
            "area": dec.area,
            "need": dec.need,
            "min_level": dec.min_level,
            "snapshot": dec.snapshot,
        }
        try:
            print("[ester-will-guard][DENY]", json.dumps(body, ensure_ascii=False))
        except Exception:
            pass
        return jsonify(body), 403

    print(f"[ester-will-guard] HTTP guard registered (mode={_ab_mode()})")

__all__ = ["register"]
