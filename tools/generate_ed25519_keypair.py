# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.runtime import evidence_signing


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate Ester evidence Ed25519 keypair.")
    ap.add_argument("--priv", default="", help="Private key PEM path.")
    ap.add_argument("--pub", default="", help="Public key PEM path.")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing keypair.")
    args = ap.parse_args()

    rep = evidence_signing.ensure_keypair(
        priv_path=str(args.priv or ""),
        pub_path=str(args.pub or ""),
        overwrite=bool(args.overwrite),
    )
    print(json.dumps(rep, ensure_ascii=True, indent=2))
    return 0 if bool(rep.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())

