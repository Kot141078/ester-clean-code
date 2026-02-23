# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Dict, List


DEFAULT_RELPATHS = [
    "modules/garage/agent_factory.py",
    "modules/garage/templates/pack_v1.py",
    "modules/garage/templates/registry.py",
]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(131072)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _manifest_fingerprint(files: List[Dict[str, object]]) -> str:
    src = "|".join(
        [
            f"{str(row.get('relpath') or '')}:{str(row.get('sha256') or '')}:{int(row.get('size') or 0)}"
            for row in files
        ]
    )
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def _collect_files(root: Path, relpaths: List[str]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    seen = set()
    for raw in list(relpaths or []):
        rel = str(raw or "").strip().replace("\\", "/")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        p = (root / rel).resolve()
        if not p.exists() or (not p.is_file()):
            continue
        out.append(
            {
                "relpath": rel,
                "sha256": _sha256_file(p),
                "size": int(p.stat().st_size),
            }
        )
    out.sort(key=lambda x: str(x.get("relpath") or ""))
    return out


def build_manifest(*, root: Path, out_path: Path, relpaths: List[str]) -> Dict[str, object]:
    root = root.resolve()
    files = _collect_files(root, relpaths)
    payload: Dict[str, object] = {
        "schema": "ester.integrity.manifest.v1",
        "created_ts": int(time.time()),
        "root": str(root),
        "files": files,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "manifest_path": str(out_path),
        "root": str(root),
        "count": len(files),
        "fingerprint": _manifest_fingerprint(files),
        "files": files,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build template/capability integrity manifest.")
    ap.add_argument("--root", default=".", help="Project root for relpaths.")
    ap.add_argument(
        "--out",
        default="data/integrity/template_capability_SHA256SUMS.json",
        help="Manifest output path.",
    )
    ap.add_argument(
        "--relpath",
        action="append",
        default=[],
        help="Extra relpath to include; may be provided multiple times.",
    )
    args = ap.parse_args()

    root = Path(str(args.root or ".")).resolve()
    out = Path(str(args.out or "").strip())
    if not out.is_absolute():
        out = (root / out).resolve()

    relpaths = list(DEFAULT_RELPATHS)
    for extra in list(args.relpath or []):
        rp = str(extra or "").strip().replace("\\", "/")
        if rp and rp not in relpaths:
            relpaths.append(rp)

    rep = build_manifest(root=root, out_path=out, relpaths=relpaths)
    print(json.dumps(rep, ensure_ascii=True, indent=2))
    return 0 if bool(rep.get("ok")) and int(rep.get("count") or 0) > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

