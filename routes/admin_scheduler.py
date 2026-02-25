# -*- coding: utf-8 -*-
"""Admin Scheduler - offlayn tik-scanner inbox → ochered (bez demonov).

Most (yavnyy):
- (Kibernetika ↔ UX) Ruchnoy “tik” upravlyaetsya polzovatelem: Scan=nablyudaem, Apply=deystvuem.

Mosty (skrytye):
- (Infoteoriya ↔ Ekonomika) Limity i dedup snizhayut entropiyu i stoimost pererabotki.
- (Logika ↔ Nadezhnost) Zhestkiy A/B-predokhranitel predotvraschaet neozhidannye zapisi.

Zemnoy abzats:
Stranitsa pozvolyaet offlayn proverit vkhodyaschie fayly i v rezhime B polozhit zadaniya
v `ESTER/state/queue/*.json`. Po umolchaniyu vse vyklyucheno; nikakikh fonovykh potokov.

c=a+b"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from flask import Blueprint, jsonify, render_template, request

# We do not change contracts: import paths are as in the dump
from modules.scheduler.watcher import WatchConfig, plan_tick, apply_tick  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_scheduler", __name__, url_prefix="/admin/scheduler")

# A/B slot for secure self-editing
AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()

# Konfig v state (drop-in sovmestimost)
CFG_FILE = Path("ESTER/state/scheduler/config.json")
CFG_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_cfg() -> WatchConfig:
    if CFG_FILE.exists():
        try:
            data = json.loads(CFG_FILE.read_text(encoding="utf-8"))
            return WatchConfig(**data)  # type: ignore[arg-type]
        except Exception:
            # We return the default configuration, it doesn’t crash
            pass
    return WatchConfig()  # type: ignore[call-arg]


def _save_cfg(cfg: WatchConfig) -> None:
    # Bezopasno - konfig v ESTER/state
    CFG_FILE.write_text(
        json.dumps(asdict(cfg), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@bp.get("/")
def page():
    cfg = _load_cfg()
    return render_template("admin_scheduler.html", ab_mode=AB_MODE, cfg=asdict(cfg), last=None)


@bp.post("/scan")
def api_scan():
    cfg = _load_cfg()
    res = plan_tick(cfg)
    return jsonify(res)


@bp.post("/apply")
def api_apply():
    cfg = _load_cfg()
    try:
        # Optional updating of limits/flags from the form
        if request.is_json:
            data: Dict[str, Any] = request.get_json(silent=True) or {}
        else:
            data = request.form.to_dict()
        if data:
            cfg = WatchConfig(
                include_txt=str(data.get("include_txt", cfg.include_txt)).lower() in {"1", "true", "yes", "on"},
                include_md=str(data.get("include_md", cfg.include_md)).lower() in {"1", "true", "yes", "on"},
                include_pdf=str(data.get("include_pdf", cfg.include_pdf)).lower() in {"1", "true", "yes", "on"},
                limit_files=int(data.get("limit_files", cfg.limit_files)),
                max_bytes=int(data.get("max_bytes", cfg.max_bytes)),
                enable_chunking=str(data.get("enable_chunking", cfg.enable_chunking)).lower() in {"1", "true", "yes", "on"},
                chunk_target=int(data.get("chunk_target", cfg.chunk_target)),
            )
            _save_cfg(cfg)
    except Exception:
        # Quietly ignore input if it is invalid; we use the old sfg
        pass

    res = apply_tick(cfg)
    return jsonify(res)


def register(app):  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    # Compatible initialization hook (pattern from dump)
    register(app)


__all__ = ["bp", "register", "init_app"]