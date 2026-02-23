# -*- coding: utf-8 -*-
"""
routes/storage_targets_routes.py - REST API dlya upravleniya tselyami khraneniya i zagruzki artefaktov.

Endpointy (JWT trebuetsya):
  GET    /storage/targets               - spisok targetov
  POST   /storage/targets               - dobavit/obnovit target (po id, esli ukazan)
  DELETE /storage/targets/<id>          - udalit
  POST   /storage/targets/<id>/test     - proverit dostupnost
  POST   /storage/upload                - zagruzit fayl na odin ili vse targety

Telo POST /storage/targets:
  { "id": "t_...", "type": "local|s3|webdav|email", "name": "...", "enabled": true, "config": {...} }

Telo POST /storage/upload:
  { "path": "/abs/path/to/file.zip", "targets": ["t_1","t_2"] }  # esli targets net - gruzim na vse enabled

Bezopasnost:
  • Pered setevymi deystviyami - soft-preduprezhdenie (guardian.check_action); kvorm mozhno delat cherez releases API.

Mosty:
- Yavnyy: (Khranilischa ↔ Veb) edinyy REST-sloy dlya konfiguratsii i zagruzok v raznye storadzhi.
- Skrytyy #1: (Bezopasnost ↔ Operatsii) myagkaya proverka guardian snizhaet riski nesanktsionirovannykh rassylok.
- Skrytyy #2: (Infoteoriya ↔ Ekonomiya) vyborochnaya zagruzka po spisku targets ogranichivaet shum i lishniy trafik.

Zemnoy abzats:
Dumay o module kak o «raspredelitele na polkakh»: nastroil polki (targety), polozhil fayl - on okazalsya tam, gde nado.
Bezopasnost prikryvaet vneshnie napravleniya, a API ostaetsya prostym i predskazuemym.

# c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Myagkie importy - modul ne dolzhen padat pri otsutstvii nekotorykh podsistem
try:  # pragma: no cover
    from modules.safety.guardian import check_action  # type: ignore
except Exception:  # pragma: no cover
    def check_action(kind: str, ctx: Dict[str, Any]) -> Dict[str, Any]:  # type: ignore
        return {"ok": True, "risk": "unknown"}

try:  # pragma: no cover
    from modules.storage.targets import (  # type: ignore
        add_target,
        get_target,
        list_targets,
        remove_target,
        update_target,
    )
except Exception:  # pragma: no cover
    add_target = get_target = list_targets = remove_target = update_target = None  # type: ignore

try:  # pragma: no cover
    from modules.storage.uploader import test_target, upload_file  # type: ignore
except Exception:  # pragma: no cover
    test_target = upload_file = None  # type: ignore

storage_bp = Blueprint("storage_targets", __name__, url_prefix="/storage")


def _targets_available() -> bool:
    return all(f is not None for f in (add_target, get_target, list_targets, remove_target, update_target))


@storage_bp.get("/targets")
@jwt_required()
def api_list():
    if list_targets is None:
        return jsonify({"ok": False, "error": "storage_targets_unavailable"}), 500
    try:
        return jsonify({"ok": True, "items": list_targets(include_disabled=True)})  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@storage_bp.post("/targets")
@jwt_required()
def api_add_or_update():
    if not _targets_available():
        return jsonify({"ok": False, "error": "storage_targets_unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    if not data.get("type"):
        return jsonify({"ok": False, "error": "type required"}), 400
    try:
        if data.get("id"):
            res = update_target(data["id"], {k: v for k, v in data.items() if k != "id"})  # type: ignore[misc]
            return jsonify(res if isinstance(res, dict) else {"ok": True, "result": res})
        else:
            res = add_target(data)  # type: ignore[misc]
            return jsonify(res if isinstance(res, dict) else {"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@storage_bp.delete("/targets/<tid>")
@jwt_required()
def api_delete(tid: str):
    if remove_target is None:
        return jsonify({"ok": False, "error": "storage_targets_unavailable"}), 500
    try:
        return jsonify(remove_target(tid))  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@storage_bp.post("/targets/<tid>/test")
@jwt_required()
def api_test(tid: str):
    if get_target is None or test_target is None:
        return jsonify({"ok": False, "error": "storage_targets_unavailable"}), 500
    try:
        t = get_target(tid)  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    if not t:
        return jsonify({"ok": False, "error": "not found"}), 404

    # soft check
    try:
        if t.get("type") in ("s3", "webdav", "email"):
            risk = (check_action("p2p_broadcast", {"target": t}) or {}).get("risk")
            if risk == "forbid":
                return jsonify({"ok": False, "error": "forbidden by guardian"}), 403
    except Exception:
        pass

    try:
        return jsonify(test_target(t))  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@storage_bp.post("/upload")
@jwt_required()
def api_upload():
    if get_target is None or list_targets is None or upload_file is None:
        return jsonify({"ok": False, "error": "storage_targets_unavailable"}), 500

    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    path = str(data.get("path") or "")
    if not path or not os.path.exists(path):
        return jsonify({"ok": False, "error": "path not found"}), 400

    selected = data.get("targets")
    targets: List[Dict[str, Any]]
    try:
        if selected:
            targets = [get_target(tid) for tid in selected]  # type: ignore[misc]
            targets = [t for t in targets if t]
        else:
            targets = [t for t in list_targets(include_disabled=False) if t.get("enabled", True)]  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    if not targets:
        return jsonify({"ok": False, "error": "no targets"}), 400

    results: List[Dict[str, Any]] = []
    for t in targets:
        try:
            if t.get("type") in ("s3", "webdav", "email"):
                # Seychas - preduprezhdeniya tolko v logike klienta/UI
                _ = check_action("p2p_broadcast", {"target": t})
        except Exception:
            pass
        try:
            res = upload_file(t, path, None)  # type: ignore[misc]
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        results.append({"id": t.get("id"), **(res if isinstance(res, dict) else {"ok": True, "result": res})})

    ok = all(bool(r.get("ok")) for r in results)
    return jsonify({"ok": ok, "results": results})


def register_storage_routes(app) -> None:  # pragma: no cover
    """Istoricheskaya registratsiya blyuprinta (sovmestimost)."""
    app.register_blueprint(storage_bp)


# Unifitsirovannye khuki proekta
def register(app) -> None:  # pragma: no cover
    app.register_blueprint(storage_bp)


def init_app(app) -> None:  # pragma: no cover
    app.register_blueprint(storage_bp)


__all__ = ["storage_bp", "register_storage_routes", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(storage_bp)
    return app