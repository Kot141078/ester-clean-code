# -*- coding: utf-8 -*-
"""
scripts/self_save_everywhere.py — otpravit poslednie relizy na vse nastroennye targety.

Po umolchaniyu berem vse arkhivy v PERSIST_DIR/self/archives/*.zip i shlem na enabled-targety.
Mozhno ukazat konkretnyy fayl ili CID.

Primery:
  python -m scripts.self_save_everywhere
  python -m scripts.self_save_everywhere --cid <CID>
  python -m scripts.self_save_everywhere --path /path/to/archive.zip --targets t_1 t_2
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from typing import Any, Dict, List

from modules.selfmanage.archive import _archives_dir as _local_archives_dir  # type: ignore
from modules.storage.targets import get_target, list_targets
from modules.storage.uploader import upload_file
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _find_archive(path: str | None, cid: str | None) -> List[str]:
    if path:
        p = os.path.abspath(path)
        return [p] if os.path.exists(p) else []
    if cid:
        p = os.path.join(_local_archives_dir(), f"{cid}.zip")
        return [p] if os.path.exists(p) else []
    return sorted(glob.glob(os.path.join(_local_archives_dir(), "*.zip")))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Save Ester releases to all targets")
    ap.add_argument("--path", type=str, default=None, help="Put k odnomu arkhivu")
    ap.add_argument("--cid", type=str, default=None, help="CID reliza")
    ap.add_argument(
        "--targets",
        nargs="*",
        help="Spisok id targetov (po umolchaniyu — vse enabled)",
        default=None,
    )
    args = ap.parse_args(argv)

    archives = _find_archive(args.path, args.cid)
    if not archives:
        print(json.dumps({"ok": False, "error": "no archives found"}, ensure_ascii=False))
        return 2

    if args.targets:
        targets = [t for t in (get_target(tid) for tid in args.targets) if t]
    else:
        targets = [t for t in list_targets(include_disabled=False) if t.get("enabled", True)]
    if not targets:
        print(json.dumps({"ok": False, "error": "no targets"}, ensure_ascii=False))
        return 2

    summary: Dict[str, Any] = {"ok": True, "uploaded": []}
    for arc in archives:
        name = os.path.basename(arc)
        res_line = {"archive": name, "to": []}
        for t in targets:
            res = upload_file(t, arc, None)
            res_line["to"].append({"target": t["id"], **res})
        summary["uploaded"].append(res_line)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(all(x.get("ok") for x in line["to"]) for line in summary["uploaded"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())