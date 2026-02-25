# -*- coding: utf-8 -*-
"""modules/social/ledger.py - uchet publikatsiy, prosmotrov i dokhodov po platformam/kampaniyam.

Mosty:
- Yavnyy: (Uchet ↔ Prozrachnost/Finansy) svodka postsov/metrik dlya UI/otchetov, s aggregates.
- Skrytyy #1: (Memory ↔ Profile) kazhdaya zapis fiksiruetsya s profileom dlya audita.
- Skrytyy #2: (Garazh ↔ Ekonomika/Strategiya) dannye dlya podscheta dokhodov/okhvata, dostupny dlya avtoplanirovaniya.

Zemnoy abzats:
Eto "umnaya tetrad" s tablichkami: kogda, kuda opublikovali, skolko prosmotrov/deneg - vse v odnom meste, s eksportom i aggregates, chtoby Papa ulybnulsya, a Ester ne poteryala ni kopeyki konteksta.

# c=a+b"""
from __future__ import annotations
import os, json, time, csv
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

LEDGER = os.getenv("SOCIAL_LEDGER", "data/social/ledger.json")

def _ensure():
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    if not os.path.isfile(LEDGER):
        json.dump({"rows": []}, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load() -> Dict[str, Any]:
    _ensure()
    try:
        return json.load(open(LEDGER, "r", encoding="utf-8"))
    except Exception:
        return {"rows": []}  # Falbatsk to empty if damaged

def _save(j: Dict[str, Any]):
    try:
        json.dump(j, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass  # Doesn't break the flow, but can be logged in the future

def _mm_pass(note: str, meta: Dict[str, Any], source: str = "social://ledger") -> None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm = get_mm()
        upsert_with_passport(mm, note, meta, source=source)
    except Exception:
        pass

def record(platform: str, campaign: str, metric: str, value: float, currency: str | None = None, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    j = _load()
    row = {
        "ts": int(time.time()),
        "platform": platform,
        "campaign": campaign,
        "metric": metric,
        "value": float(value),
        "currency": currency or "",
        "extra": dict(extra or {})
    }
    j["rows"].append(row)
    _save(j)
    _mm_pass("Sots-metrika zapisana", row)
    return {"ok": True, "row": row}

def list_all() -> Dict[str, Any]:
    j = _load()
    rows = j.get("rows", [])
    # Expanded aggregates: totals i averages po platform/metric/campaign
    totals: Dict[tuple, float] = {}
    counts: Dict[tuple, int] = {}
    for r in rows:
        key = (r["platform"], r["campaign"], r["metric"])
        totals[key] = totals.get(key, 0.0) + float(r.get("value", 0.0))
        counts[key] = counts.get(key, 0) + 1
    aggr = [
        {"platform": k[0], "campaign": k[1], "metric": k[2], "total": v, "average": v / counts[k] if counts[k] > 0 else 0.0}
        for k, v in totals.items()
    ]
    return {"ok": True, "rows": rows, "summary": aggr}

def list_posts() -> Dict[str, Any]:
    """Alias ​​for viewing only posts (metrics=capacity)."""
    all_data = list_all()
    posts = [r for r in all_data["rows"] if r.get("metric") == "post"]
    return {"ok": True, "posts": posts}

def export_to_csv(csv_path: str) -> Dict[str, Any]:
    """Export ROVs to DSV for UI/reports."""
    j = _load()
    rows = j.get("rows", [])
    if not rows:
        return {"ok": False, "error": "no_data"}
    try:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["ts", "platform", "campaign", "metric", "value", "currency", "extra"])
            writer.writeheader()
            for row in rows:
                row["extra"] = json.dumps(row["extra"], ensure_ascii=False)  # Flatten extra
                writer.writerow(row)
        return {"ok": True, "path": csv_path, "rows_exported": len(rows)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
