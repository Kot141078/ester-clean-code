"""Build minimized operator pointers for SYNAPS Codex handoffs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    from modules.synaps import (
        CODEX_HANDOFF_POINTER_CONFIRM_PHRASE,
        DEFAULT_CODEX_HANDOFF_POINTER_ROOT,
        build_codex_handoff_pointer,
        write_codex_handoff_pointer,
    )

    parser = argparse.ArgumentParser(description="Create a minimized operator pointer for Codex handoff relay.")
    parser.add_argument("--gate", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--transfer-id", action="append", default=[])
    parser.add_argument("--rejected-transfer-id", action="append", default=[])
    parser.add_argument("--source-file", action="append", default=[])
    parser.add_argument("--patch-sha256", default="")
    parser.add_argument("--note", default="")
    parser.add_argument("--forbid-term", action="append", default=[])
    parser.add_argument("--output", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--confirm", default="", help=f"Required for --write: {CODEX_HANDOFF_POINTER_CONFIRM_PHRASE}")
    args = parser.parse_args(argv)

    output = args.output or str(Path(DEFAULT_CODEX_HANDOFF_POINTER_ROOT) / f"{args.gate}_pointer.md")
    payload = build_codex_handoff_pointer(
        gate=args.gate,
        title=args.title,
        accepted_transfer_ids=args.transfer_id,
        rejected_transfer_ids=args.rejected_transfer_id,
        source_files=args.source_file,
        patch_sha256=args.patch_sha256,
        note=args.note,
        forbid_terms=args.forbid_term,
    )
    if args.write:
        payload["write"] = write_codex_handoff_pointer(payload, output_path=output, confirm=args.confirm)
        payload["ok"] = bool(payload["ok"] and payload["write"].get("ok"))
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
