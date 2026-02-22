# -*- coding: utf-8 -*-
"""
Most mezhdu voley Ester i selfmod.

Endpointy:
    GET  /ester/selfmod/will_plan
    POST /ester/selfmod/propose_guarded

Naznachenie:
- Davat svodnyy vid (will + selfmod) dlya verkhnego sloya.
- Prinimat formalnye zaprosy na patchi:
    * source="ester"  — kandidat na samoizmenenie (cherez strogiy guard).
    * lyubye drugie    — prokidyvaem k /ester/selfmod/propose kak est (operator).

Bezopasnost:
- Rezhim A: Ester nikogda ne pishet. Tolko introspect.
- Rezhim B: Ester mozhet pisat tolko v belyy spisok putey i tolko esli
  ESTER_SELFMOD_ALLOW_ESTER=1.
"""

import os
import json
from typing import Any, Dict, List
from urllib import request as urlrequest, error as urlerror
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ester_selfmod_will = Blueprint("ester_selfmod_will", __name__)

DEFAULT_HOST = os.getenv("ESTER_HTTP_HOST", "127.0.0.1")
DEFAULT_PORT = os.getenv("ESTER_HTTP_PORT", "8080")

SELFMOD_MODE = (os.getenv("ESTER_SELFMOD_AB", "A") or "A").strip().upper()
ALLOW_ESTER = (os.getenv("ESTER_SELFMOD_ALLOW_ESTER", "0") or "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# Kuda Ester mozhet pisat sama
SAFE_ESTER_PREFIXES = (
    "modules/ester/",
)


def _fetch_json(path: str) -> Dict[str, Any]:
    base = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    url = base + path
    try:
        with urlrequest.urlopen(url, timeout=2.0) as resp:
            code = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw": body}
            return {"code": code, "data": data}
    except urlerror.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {"raw": body}
        return {"code": e.code, "data": data}
    except Exception as e:
        return {"code": 503, "data": {"ok": False, "error": str(e)}}


def _post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    base = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    url = base + path
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=5.0) as resp:
            code = resp.getcode()
            text = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(text)
            except Exception:
                data = {"raw": text}
            return {"code": code, "data": data}
    except urlerror.HTTPError as e:
        try:
            text = e.read().decode("utf-8", errors="replace")
        except Exception:
            text = ""
        try:
            data = json.loads(text) if text else {}
        except Exception:
            data = {"raw": text}
        return {"code": e.code, "data": data}
    except Exception as e:
        return {"code": 503, "data": {"ok": False, "error": str(e)}}


def _is_safe_ester_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in SAFE_ESTER_PREFIXES)


def _normalize_changes(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Podderzhivaem dva formata:
    1) changes: [ {path, content}, ... ]
    2) path + (content | patch.content) — oborachivaem v changes[1].
    """
    if "changes" in body and isinstance(body["changes"], list):
        out = []
        for ch in body["changes"]:
            if not isinstance(ch, dict):
                continue
            path = str(ch.get("path") or "").strip()
            content = ch.get("content")
            if path and isinstance(content, str):
                out.append({"path": path, "content": content})
        return out

    path = str(body.get("path") or "").strip()
    if not path:
        return []

    content = body.get("content")
    patch = body.get("patch")
    if content is None and isinstance(patch, dict):
        content = patch.get("content")

    if isinstance(content, str):
        return [{"path": path, "content": content}]

    return []


@bp_ester_selfmod_will.route("/ester/selfmod/will_plan", methods=["GET"])
def ester_selfmod_will_plan():
    selfmod_status = _fetch_json("/ester/selfmod/status")
    will_plan = _fetch_json("/ester/will/plan")

    result = {
        "ok": True,
        "mode": SELFMOD_MODE,
        "allow_ester": ALLOW_ESTER,
        "selfmod": selfmod_status,
        "will": will_plan,
    }
    return jsonify(result)


@bp_ester_selfmod_will.route("/ester/selfmod/propose_guarded", methods=["POST"])
def ester_selfmod_propose_guarded():
    # Bazovyy karkas otveta
    guard_info: List[Dict[str, Any]] = []

    try:
        body = request.get_json(force=True, silent=False) or {}
    except Exception:
        return (
            jsonify(
                {
                    "ok": False,
                    "mode": SELFMOD_MODE,
                    "status_code": 400,
                    "error": "invalid_json",
                }
            ),
            400,
        )

    source = str(body.get("source") or "operator").strip().lower()
    changes = _normalize_changes(body)

    # === VETKA: Ester prosit o patche ===
    if source == "ester":
        g = {
            "mode": SELFMOD_MODE,
            "source": "ester",
            "allow_ester": ALLOW_ESTER,
            "path": "",
            "note": "",
        }

        # Ester zapreschena po statusu
        if not ALLOW_ESTER:
            g["note"] = "ester_not_allowed_by_selfmod_status"
            guard_info.append(g)
            return jsonify(
                {
                    "ok": False,
                    "mode": SELFMOD_MODE,
                    "status_code": 403,
                    "guard": guard_info,
                    "result": {
                        "ok": False,
                        "note": g["note"],
                    },
                }
            )

        # Rezhim A — tolko introspect, ne pishem na disk
        if SELFMOD_MODE == "A":
            g["note"] = "introspect_only_mode_A"
            guard_info.append(g)
            return jsonify(
                {
                    "ok": False,
                    "mode": SELFMOD_MODE,
                    "status_code": 200,
                    "guard": guard_info,
                    "result": {
                        "ok": False,
                        "note": g["note"],
                    },
                }
            )

        # Rezhim B + Ester razreshena — proveryaem izmeneniya
        if not changes:
            g["note"] = "no_valid_changes"
            guard_info.append(g)
            return jsonify(
                {
                    "ok": False,
                    "mode": SELFMOD_MODE,
                    "status_code": 400,
                    "guard": guard_info,
                    "result": {
                        "ok": False,
                        "errors": ["no_valid_changes"],
                        "note": "proposal_invalid",
                    },
                }
            )

        safe_changes: List[Dict[str, Any]] = []
        for idx, ch in enumerate(changes):
            path = ch["path"]
            allowed = _is_safe_ester_path(path)
            note = "ok" if allowed else f"forbidden_target:{path}"
            guard_info.append(
                {
                    "idx": idx,
                    "path": path,
                    "allowed": allowed,
                    "note": note,
                }
            )
            if allowed:
                safe_changes.append({"path": path, "content": ch["content"]})

        if not safe_changes:
            return jsonify(
                {
                    "ok": False,
                    "mode": SELFMOD_MODE,
                    "status_code": 400,
                    "guard": guard_info,
                    "result": {
                        "ok": False,
                        "errors": ["no_valid_changes"],
                        "note": "proposal_invalid",
                    },
                }
            )

        forward_body = {
            "source": "ester",
            "reason": body.get("reason", "ester_selfmod_guarded"),
            "changes": safe_changes,
        }

        resp = _post_json("/ester/selfmod/propose", forward_body)
        code = resp.get("code", 500)
        data = resp.get("data", {})

        return jsonify(
            {
                "ok": bool(data.get("ok")) if code == 200 else False,
                "mode": SELFMOD_MODE,
                "status_code": code,
                "guard": guard_info,
                "result": data,
            }
        )

    # === VETKA: operator / vneshniy istochnik ===
    g = {
        "mode": SELFMOD_MODE,
        "source": source,
        "allow_ester": ALLOW_ESTER,
        "path": "",
        "note": "forwarded_to_selfmod_propose",
    }
    guard_info.append(g)

    resp = _post_json("/ester/selfmod/propose", body)
    code = resp.get("code", 500)
    data = resp.get("data", {})

    return jsonify(
        {
            "ok": bool(data.get("ok")) if code == 200 else False,
            "mode": SELFMOD_MODE,
            "status_code": code,
            "guard": guard_info,
            "result": data,
        }
    )