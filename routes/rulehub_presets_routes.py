# -*- coding: utf-8 -*-
"""
routes/rulehub_presets_routes.py — presety pravil myshleniya (read-only).

Endpointy:
  • GET /thinking/presets           — spisok presetov (id, title, tags)
  • GET /thinking/presets/get?id=…  — sam preset (JSON)

Mosty:
- Yavnyy: (Myshlenie v†" UX) gotovye «kartochki pravil» dlya bystroy integratsii v dvizhok mysley.
- Skrytyy #1: (Infoteoriya v†" Gistsiplina) edinyy istochnik istin dlya tipovykh pravil.
- Skrytyy #2: (Inzheneriya v†" Sovmestimost) drop-in: tolko chtenie YAML bez izmeneniy kontraktov.

Zemnoy abzats:
Eto «katalog zagotovok» — otkryl, vybral nuzhnuyu, vstavil v svoy rule set.

# c=a+b
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_rulehub_presets = Blueprint("rulehub_presets", __name__)
_CFG_PATH = os.path.join("config", "rulehub_presets.yaml")

def register(app):
    app.register_blueprint(bp_rulehub_presets)

def _parse_yaml_presets(path: str) -> List[Dict[str, Any]]:
    if not os.path.isfile(path):
        return []
    presets: List[Dict[str, Any]] = []
    cur: Dict[str, Any] | None = None
    section = None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("presets:"):
                section = "presets"; continue
            if section == "presets" and line.lstrip().startswith("- "):
                if cur:
                    presets.append(cur)
                cur = {}
                rest = line.split("- ", 1)[1].strip()
                if rest and ":" in rest:
                    k, v = rest.split(":", 1)
                    cur[k.strip()] = v.strip().strip("'").strip('"')
                continue
            if section == "presets" and ":" in s and cur is not None:
                k, v = s.split(":", 1)
                k = k.strip(); v = v.strip()
                if k in ("id", "title"):
                    cur[k] = v.strip().strip("'").strip('"')
                elif k == "tags":
                    inner = v[v.find("[")+1:-1].strip() if "[" in v and v.endswith("]") else ""
                    cur[k] = [x.strip().strip("'").strip('"') for x in inner.split(",")] if inner else []
                elif k == "rule":
                    # Nachinaetsya vlozhennyy blok YAML v†' schityvaem kak JSON-tekst po otstupam
                    cur["rule"] = {}
                else:
                    # polya rule.* v odnu glubinu
                    if "rule" not in cur:
                        cur["rule"] = {}
                    # Prostoe znachenie/slovar
                    val = v.strip().strip("'").strip('"')
                    if val.startswith("{") and val.endswith("}"):
                        try:
                            cur["rule"][k] = json.loads(val.replace("'", '"'))
                        except Exception:
                            cur["rule"][k] = val
                    else:
                        cur["rule"][k] = val
    if cur:
        presets.append(cur)
    # Normalizuem rule.when / rule.actions (esli byli serializovany kak stroki)
    for p in presets:
        rule = p.get("rule") or {}
        for fld in ("when",):
            if isinstance(rule.get(fld), str):
                try:
                    rule[fld] = json.loads(rule[fld])
                except Exception:
                    pass
        if isinstance(rule.get("actions"), str):
            try:
                rule["actions"] = json.loads(rule["actions"])
            except Exception:
                pass
        p["rule"] = rule
    return presets

@bp_rulehub_presets.route("/thinking/presets", methods=["GET"])
def list_presets():
    ps = _parse_yaml_presets(_CFG_PATH)
    listing = [{"id": p.get("id"), "title": p.get("title"), "tags": p.get("tags", [])} for p in ps]
    return jsonify({"ok": True, "presets": listing})

@bp_rulehub_presets.route("/thinking/presets/get", methods=["GET"])
def get_preset():
    pid = (request.args.get("id") or "").strip()
    if not pid:
        return jsonify({"ok": False, "error": "id is required"}), 400
    ps = _parse_yaml_presets(_CFG_PATH)
    for p in ps:
        if str(p.get("id")) == pid:
            return jsonify({"ok": True, "preset": p})
# return jsonify({"ok": False, "error": "not found"}), 404