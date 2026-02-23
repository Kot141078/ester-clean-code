# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

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


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify L4W envelope: hash + signature + optional chain head check")
    ap.add_argument("--envelope-path", required=True, help="Path under PERSIST_DIR/l4w/envelopes or absolute")
    ap.add_argument("--envelope-sha256", default="")
    ap.add_argument("--agent-id", default="")
    ns = ap.parse_args()

    raw_path = str(ns.envelope_path or "").strip()
    claimed_sha = str(ns.envelope_sha256 or "").strip().lower()
    aid = str(ns.agent_id or "").strip()

    path_rep = l4w_witness.resolve_envelope_path(raw_path)
    if not bool(path_rep.get("ok")):
        print(json.dumps({"ok": False, "error": "path_invalid", "details": path_rep}, ensure_ascii=True, indent=2))
        return 2
    p = Path(str(path_rep.get("envelope_path") or "")).resolve()
    if not p.exists() or not p.is_file():
        print(json.dumps({"ok": False, "error": "envelope_not_found", "envelope_path": str(p)}, ensure_ascii=True, indent=2))
        return 2

    actual_sha = l4w_witness.sha256_file(p)
    if claimed_sha and claimed_sha != actual_sha:
        print(
            json.dumps(
                {"ok": False, "error_code": "L4W_HASH_MISMATCH", "actual_sha256": actual_sha, "claimed_sha256": claimed_sha},
                ensure_ascii=True,
                indent=2,
            )
        )
        return 2

    envelope = _read_json(p)
    verify = l4w_witness.verify_envelope(envelope)
    if not bool(verify.get("ok")):
        print(json.dumps({"ok": False, "error": "verify_failed", "details": verify}, ensure_ascii=True, indent=2))
        return 2

    chain = {}
    if aid:
        prev_hash = str((dict(envelope.get("chain") or {})).get("prev_hash") or "").strip().lower()
        chain = l4w_witness.verify_chain_prev_hash(aid, prev_hash)

    out = {
        "ok": bool(verify.get("ok")) and (bool(chain.get("ok")) if chain else True),
        "envelope_rel_path": str(path_rep.get("envelope_rel_path") or ""),
        "envelope_sha256": actual_sha,
        "verify": verify,
        "chain": chain,
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0 if bool(out.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())

