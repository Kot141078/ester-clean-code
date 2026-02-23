# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import l4w_witness


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _parse_bool(raw: str, default: bool) -> bool:
    s = str(raw or "").strip().lower()
    if not s:
        return bool(default)
    return s in {"1", "true", "yes", "on", "y"}


def _update_reveals(reveals: List[Dict[str, Any]], *, reviewer: str, summary: str, notes: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in list(reveals or []):
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        val = row.get("value")
        if path == "claim.reviewer" and reviewer:
            val = reviewer
        elif path == "claim.summary" and summary:
            val = summary
        elif path == "claim.notes" and notes:
            val = notes
        out.append({"path": path, "salt_b64": str(row.get("salt_b64") or ""), "value": val})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build L4W disclosure packet from envelope template")
    ap.add_argument("--envelope-path", required=True)
    ap.add_argument("--template-path", default="")
    ap.add_argument("--reviewer", default="")
    ap.add_argument("--summary", default="")
    ap.add_argument("--notes", default="")
    ap.add_argument("--sign", default="1")
    ns = ap.parse_args()

    path_rep = l4w_witness.resolve_envelope_path(str(ns.envelope_path or ""))
    if not bool(path_rep.get("ok")):
        print(json.dumps({"ok": False, "error": "envelope_path_invalid", "details": path_rep}, ensure_ascii=True, indent=2))
        return 2
    envelope_path = Path(str(path_rep.get("envelope_path") or "")).resolve()
    if not envelope_path.exists():
        print(json.dumps({"ok": False, "error": "envelope_not_found", "envelope_path": str(envelope_path)}, ensure_ascii=True, indent=2))
        return 2

    template_path_raw = str(ns.template_path or "").strip()
    template_path = Path(template_path_raw).resolve() if template_path_raw else envelope_path.with_suffix(".disclosure.template.json").resolve()
    template = _read_json(template_path)
    if not template:
        print(json.dumps({"ok": False, "error": "disclosure_template_missing", "template_path": str(template_path)}, ensure_ascii=True, indent=2))
        return 2

    reveals = _update_reveals(
        list(template.get("reveals") or []),
        reviewer=str(ns.reviewer or ""),
        summary=str(ns.summary or ""),
        notes=str(ns.notes or ""),
    )
    envelope_hash = str(template.get("envelope_hash") or "").strip().lower()
    disclosure = l4w_witness.build_disclosure(
        envelope_hash,
        reveals,
        sign=_parse_bool(str(ns.sign or ""), True),
    )
    saved = l4w_witness.write_disclosure(disclosure)
    if not bool(saved.get("ok")):
        print(json.dumps({"ok": False, "error": "disclosure_write_failed", "details": saved}, ensure_ascii=True, indent=2))
        return 2

    out = {
        "ok": True,
        "template_path": str(template_path),
        "disclosure_path": str(saved.get("disclosure_path") or ""),
        "envelope_hash": envelope_hash,
        "reveals_count": len(reveals),
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

