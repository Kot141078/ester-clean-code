"""Explicit SYNAPS Codex mailbox quarantine inspector/promoter."""

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
        CODEX_MAILBOX_CONFIRM_PHRASE,
        DEFAULT_CODEX_INBOX_ROOT,
        DEFAULT_CODEX_RECEIPT_LEDGER,
        DEFAULT_QUARANTINE_ROOT,
        inspect_codex_mailbox_transfer,
        list_codex_mailbox_transfers,
        promote_codex_mailbox_transfer,
    )

    parser = argparse.ArgumentParser(description="Inspect or promote SYNAPS codex_* quarantine transfers.")
    parser.add_argument("action", choices=("list", "inspect", "promote"))
    parser.add_argument("--transfer-id", default="", help="Required for inspect/promote.")
    parser.add_argument("--quarantine-root", default=str(DEFAULT_QUARANTINE_ROOT))
    parser.add_argument("--inbox-root", default=str(DEFAULT_CODEX_INBOX_ROOT))
    parser.add_argument("--receipt-ledger", default=str(DEFAULT_CODEX_RECEIPT_LEDGER))
    parser.add_argument("--apply", action="store_true", help="Actually promote. Default is dry-run.")
    parser.add_argument("--confirm", default="", help=f"Required with --apply: {CODEX_MAILBOX_CONFIRM_PHRASE}")
    parser.add_argument("--operator", default="codex", help="Short receipt operator label.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        if args.action == "list":
            payload = list_codex_mailbox_transfers(args.quarantine_root, args.inbox_root)
        elif args.action == "inspect":
            if not args.transfer_id:
                raise ValueError("--transfer-id is required for inspect")
            payload = inspect_codex_mailbox_transfer(args.transfer_id, args.quarantine_root, args.inbox_root)
        else:
            if not args.transfer_id:
                raise ValueError("--transfer-id is required for promote")
            payload = promote_codex_mailbox_transfer(
                args.transfer_id,
                args.quarantine_root,
                args.inbox_root,
                args.receipt_ledger,
                apply=args.apply,
                confirm=args.confirm,
                operator=args.operator,
            )
    except Exception as exc:
        payload = {"ok": False, "error": exc.__class__.__name__, "message": str(exc)}

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
