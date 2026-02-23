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


def _persist_dir() -> Path:
    raw = str(os.getenv("PERSIST_DIR") or "").strip()
    if not raw:
        raw = str((ROOT / "data").resolve())
    return Path(raw).resolve()


def _resolve_evidence_path(raw: str) -> Path:
    p = Path(str(raw or "").strip())
    if p.is_absolute():
        return p.resolve()
    return (_persist_dir() / "capability_drift" / "evidence" / p).resolve()


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(raw) if isinstance(raw, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _parse_bool(raw: str, default: bool) -> bool:
    s = str(raw or "").strip().lower()
    if not s:
        return bool(default)
    return s in {"1", "true", "yes", "on", "y"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build and sign L4W envelope for drift.quarantine.clear")
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--event-id", required=True)
    ap.add_argument("--evidence-path", required=True)
    ap.add_argument("--evidence-sha256", required=True)
    ap.add_argument("--reviewer", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--notes", default="")
    ap.add_argument("--evidence-schema", default="ester.evidence.v1")
    ap.add_argument("--on-time", default="0")
    ap.add_argument("--late", default="0")
    ap.add_argument("--write-disclosure-template", default="1")
    ap.add_argument("--sign-disclosure-template", default="0")
    ns = ap.parse_args()

    aid = str(ns.agent_id or "").strip()
    event_id = str(ns.event_id or "").strip()
    evidence_path = str(ns.evidence_path or "").strip()
    evidence_sha = str(ns.evidence_sha256 or "").strip().lower()
    reviewer = str(ns.reviewer or "")
    summary = str(ns.summary or "")
    notes_raw = str(ns.notes or "")
    notes = notes_raw if notes_raw else None
    evidence_schema = str(ns.evidence_schema or "ester.evidence.v1")
    on_time = _parse_bool(str(ns.on_time or ""), False)
    late = _parse_bool(str(ns.late or ""), False)
    write_template = _parse_bool(str(ns.write_disclosure_template or ""), True)
    sign_template = _parse_bool(str(ns.sign_disclosure_template or ""), False)

    if not aid or not event_id:
        print(json.dumps({"ok": False, "error": "agent_id_or_event_id_required"}, ensure_ascii=True, indent=2))
        return 2
    if len(evidence_sha) != 64:
        print(json.dumps({"ok": False, "error": "evidence_sha256_invalid"}, ensure_ascii=True, indent=2))
        return 2

    evidence_sig_ok = False
    evidence_payload_hash = ""
    evidence_file = _resolve_evidence_path(evidence_path)
    if evidence_file.exists() and evidence_file.is_file():
        packet = _read_json(evidence_file)
        evidence_schema = str(packet.get("schema") or evidence_schema)
        sig = dict(packet.get("sig") or {})
        evidence_sig_ok = bool(sig)
        evidence_payload_hash = str(sig.get("payload_hash") or "")

    head = l4w_witness.chain_head(aid)
    prev_hash = str(head.get("envelope_hash") or "").strip().lower() if bool(head.get("has_head")) else ""

    built = l4w_witness.build_envelope_for_clear(
        aid,
        event_id,
        reviewer=reviewer,
        summary=summary,
        notes=notes,
        evidence_path=evidence_path,
        evidence_sha256=evidence_sha,
        evidence_schema=evidence_schema,
        evidence_sig_ok=bool(evidence_sig_ok),
        evidence_payload_hash=evidence_payload_hash,
        prev_hash=prev_hash,
        on_time=bool(on_time),
        late=bool(late),
    )
    if not bool(built.get("ok")):
        print(json.dumps({"ok": False, "error": "envelope_build_failed", "details": built}, ensure_ascii=True, indent=2))
        return 2

    sign = l4w_witness.sign_envelope(dict(built.get("envelope") or {}))
    if not bool(sign.get("ok")):
        print(json.dumps({"ok": False, "error": "envelope_sign_failed", "details": sign}, ensure_ascii=True, indent=2))
        return 2

    envelope = dict(sign.get("envelope") or {})
    write = l4w_witness.write_envelope(aid, envelope)
    if not bool(write.get("ok")):
        print(json.dumps({"ok": False, "error": "envelope_write_failed", "details": write}, ensure_ascii=True, indent=2))
        return 2

    disclosure_template_path = ""
    if write_template:
        template = dict(built.get("disclosure_template") or {})
        template["envelope_hash"] = str(sign.get("envelope_hash") or "")
        if sign_template:
            template = l4w_witness.build_disclosure(
                str(sign.get("envelope_hash") or ""),
                list(template.get("reveals") or []),
                sign=True,
            )
        out_path = Path(str(write.get("envelope_path") or "")).with_suffix(".disclosure.template.json").resolve()
        _write_json(out_path, template)
        disclosure_template_path = str(out_path)

    out = {
        "ok": True,
        "agent_id": aid,
        "event_id": event_id,
        "envelope_path": str(write.get("envelope_rel_path") or ""),
        "envelope_sha256": str(write.get("envelope_sha256") or ""),
        "envelope_hash": str(sign.get("envelope_hash") or ""),
        "prev_hash": str((dict(envelope.get("chain") or {})).get("prev_hash") or ""),
        "pub_fingerprint": str(sign.get("pub_fingerprint") or ""),
        "disclosure_template_path": disclosure_template_path,
    }
    print(json.dumps(out, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
