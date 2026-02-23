# -*- coding: utf-8 -*-
"""
routes/provenance_network_routes.py — setevye ruchki dlya obmena «profileami znaniy» (provenance).

Endpointy:
  • GET  /p2p/provenance/export?limit=N
  • POST /p2p/provenance/announce   {"passports":[{sha256,len,source?,ts?},...]}
  • POST /p2p/provenance/verify     {"passports":[{sha256,...}]}

Mosty:
- Yavnyy: (Memory v†" Set) obyavlyaem szhatye metadannye znaniy bez peredachi soderzhimogo.
- Skrytyy #1: (Infoteoriya v†" Nadezhnost) sveryaem sha256 pered obmenom — ne zaprashivaem lishnee.
- Skrytyy #2: (Kibernetika v†" Masshtab) batchi JSON bez vneshnikh zavisimostey.

Zemnoy abzats:
Eto kak spisok nakladnykh mezhdu skladami: soobschaem nomera korobok i sveryaemsya, nuzhno li voobsche vezti.

# c=a+b
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_prov_net = Blueprint("prov_net", __name__)

try:
    from modules.memory.provenance import stats_index  # type: ignore
except Exception:
    stats_index = None  # type: ignore

_PROV_DIR = os.path.join("data", "provenance")
_LOG = os.path.join(_PROV_DIR, "passports.jsonl")

def register(app):
    app.register_blueprint(bp_prov_net)

def _iter_passports(limit: int) -> List[Dict[str, Any]]:
    if not os.path.isfile(_LOG):
        return []
    rows: List[Dict[str, Any]] = []
    with open(_LOG, "r", encoding="utf-8") as f:
        lines = f.readlines()[-max(1, limit):]
    for s in lines:
        try:
            j = json.loads(s)
            # unifitsiruem eksport
            rows.append({"sha256": j.get("sha256"), "len": j.get("len"), "source": j.get("source"), "ts": j.get("ts")})
        except Exception:
            continue
    return rows

@bp_prov_net.route("/p2p/provenance/export", methods=["GET"])
def api_export():
    try:
        limit = int(request.args.get("limit", "100"))
    except Exception:
        limit = 100
    return jsonify({"ok": True, "passports": _iter_passports(limit)})

@bp_prov_net.route("/p2p/provenance/announce", methods=["POST"])
def api_announce():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    ps: List[Dict[str, Any]] = list(data.get("passports") or [])
    if not ps:
        return jsonify({"ok": True, "added": 0})
    os.makedirs(_PROV_DIR, exist_ok=True)
    added = 0
    # akkuratnoe dopolnenie indeksa (bez dubley po sha256+source)
    seen = set()
    if os.path.isfile(_LOG):
        try:
            for line in open(_LOG, "r", encoding="utf-8"):
                try:
                    j = json.loads(line)
                    seen.add((j.get("sha256"), json.dumps(j.get("source", {}), sort_keys=True)))
                except Exception:
                    continue
        except Exception:
            pass
    with open(_LOG, "a", encoding="utf-8") as f:
        for p in ps:
            key = (p.get("sha256"), json.dumps(p.get("source", {}), sort_keys=True))
            if key in seen:
                continue
            row = {"sha256": p.get("sha256"), "len": p.get("len"), "source": p.get("source", {}), "ts": int(p.get("ts") or 0)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            added += 1
    return jsonify({"ok": True, "added": added})

@bp_prov_net.route("/p2p/provenance/verify", methods=["POST"])
def api_verify():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    ps: List[Dict[str, Any]] = list(data.get("passports") or [])
    wants = {str(p.get("sha256")) for p in ps if p.get("sha256")}
    have = set()
    if os.path.isfile(_LOG):
        try:
            for line in open(_LOG, "r", encoding="utf-8"):
                try:
                    j = json.loads(line)
                    h = str(j.get("sha256"))
                    if h in wants:
                        have.add(h)
                except Exception:
                    continue
        except Exception:
            pass
    missing = sorted(list(wants - have))
    return jsonify({"ok": True, "missing": missing, "have": sorted(list(have))})
