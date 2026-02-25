# -*- coding: utf-8 -*-
"""modules/proactive/video_subs_cfg.py - chtenie/zapis konfiguratsii podpisok (config/video_subscriptions.yaml).

Format sovmestim s uzhe vydannym faylom config/video_subscriptions.yaml.
Podderzhivayutsya operatsii: load_all(), upsert(sub), delete(sub_id), toggle(sub_id, enabled).

Mosty:
- Yavnyy: (Infoteoriya ↔ Inzheneriya) Edinyy format YAML dlya podpisok snizhaet entropiyu upravleniya potokami.
- Skrytyy #1: (Kibernetika ↔ Nadezhnost) Validatsiya i normalizatsiya zapisey pered sokhraneniem — ustoychivost k oshibkam vvoda.
- Skrytyy #2: (Memory ↔ Operatsii) Config - dolgovremennaya “pamyat namereniy” operatora, upravlyayuschaya povedeniem proaktiva.

Zemnoy abzats:
Eto kak “kartoteka klapanov” na trube: kazhdaya kartochka - istochnik; flazhok enabled - polozhenie klapana; fayl - obschiy schit avtomatiki.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_CFG_PATH = os.path.join("config", "video_subscriptions.yaml")

def _ensure_path() -> None:
    d = os.path.dirname(_CFG_PATH)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    if not os.path.isfile(_CFG_PATH):
        with open(_CFG_PATH, "w", encoding="utf-8") as f:
            f.write("""subscriptions: []\n""")

def _parse_scalar(v: str):
    v = v.strip()
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    if v.startswith("'") and v.endswith("'"):
        return v[1:-1]
    if v.isdigit():
        try:
            return int(v)
        except Exception:
            return v
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.endswith("]") and "[" in v:
        inner = v[v.find("[")+1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip("'").strip('"') for x in inner.split(",")]
    return v

def _dump_scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        items = []
        for x in v:
            if isinstance(x, str):
                items.append(f"'{x}'")
            else:
                items.append(str(x))
        return "[" + ", ".join(items) + "]"
    s = str(v)
    # wrap in quotes if there are colons/spaces
    if (":" in s) or (" " in s):
        return f"\"{s}\""
    return s

def load_all() -> List[Dict[str, Any]]:
    """Vozvraschaet spisok slovarey podpisok."""
    _ensure_path()
    subs: List[Dict[str, Any]] = []
    cur = None
    with open(_CFG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")
            if not raw.strip() or raw.strip().startswith("#"):
                continue
            if raw.startswith("subscriptions:"):
                continue
            if raw.lstrip().startswith("- "):
                if cur:
                    subs.append(cur)
                cur = {}
                rest = raw.split("- ", 1)[1].strip()
                if rest and ":" in rest:
                    k, v = rest.split(":", 1)
                    cur[k.strip()] = _parse_scalar(v.strip())
                continue
            if ":" in raw and cur is not None:
                k, v = raw.split(":", 1)
                cur[k.strip()] = _parse_scalar(v.strip())
    if cur:
        subs.append(cur)
    return subs

def save_all(subs: List[Dict[str, Any]]) -> None:
    _ensure_path()
    lines = ["subscriptions:"]
    for s in subs:
        lines.append("  - id: " + _dump_scalar(s.get("id", "")))
        lines.append("    enabled: " + _dump_scalar(int(bool(s.get("enabled", 0)))))
        lines.append("    kind: " + _dump_scalar(s.get("kind", "rss")))
        if s.get("url") is not None:
            lines.append("    url: " + _dump_scalar(s.get("url")))
        if s.get("query") is not None:
            lines.append("    query: " + _dump_scalar(s.get("query")))
        lines.append("    limit: " + _dump_scalar(int(s.get("limit", 3))))
        lines.append("    tags: " + _dump_scalar(list(s.get("tags", []))))
        lines.append("")
    with open(_CFG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

def _normalize(s: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["id"] = str(s.get("id") or "").strip()
    out["enabled"] = int(s.get("enabled") or 0)
    kind = (s.get("kind") or "rss").strip()
    if kind not in ("rss", "direct", "ytsearch"):
        kind = "rss"
    out["kind"] = kind
    out["url"] = (s.get("url") or "").strip() if kind in ("rss", "direct") else None
    out["query"] = (s.get("query") or "").strip() if kind == "ytsearch" else None
    out["limit"] = int(s.get("limit") or 3)
    tags = s.get("tags") or []
    if isinstance(tags, str):
        tags = [x.strip() for x in tags.split(",") if x.strip()]
    out["tags"] = tags
    return out

def upsert(s: Dict[str, Any]) -> Dict[str, Any]:
    s = _normalize(s)
    if not s["id"]:
        raise ValueError("id is required")
    subs = load_all()
    for i, cur in enumerate(subs):
        if str(cur.get("id")) == s["id"]:
            subs[i] = {**cur, **s}
            save_all(subs)
            return subs[i]
    subs.append(s)
    save_all(subs)
    return s

def delete(sub_id: str) -> bool:
    subs = load_all()
    new = [s for s in subs if str(s.get("id")) != str(sub_id)]
    if len(new) == len(subs):
        return False
    save_all(new)
    return True

def toggle(sub_id: str, enabled: int) -> Dict[str, Any]:
    subs = load_all()
    for i, s in enumerate(subs):
        if str(s.get("id")) == str(sub_id):
            subs[i]["enabled"] = int(bool(enabled))
            save_all(subs)
            return subs[i]
# raise KeyError(f"not found: {sub_id}")