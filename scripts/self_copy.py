# -*- coding: utf-8 -*-
"""
scripts/self_copy.py — CLI: sobrat arkhiv samosokhraneniya i (optsionalno) aktivirovat reliz.
Dopolneno: zapis reliza v KG + optsionalnaya otpravka arkhiva na vybrannye targety.

Primery:
  # 1) Sobrat arkhiv iz tekuschego repo i PERSIST_DIR
  PERSIST_DIR=./data python -m scripts.self_copy build --policy-allow "/opt/ester" --policy-allow "/srv/ester"

  # 2) Pereklyuchitsya na reliz (nuzhno ESTER_MOVE_TOKEN i allowlist)
  ESTER_MOVE_TOKEN=yes python -m scripts.self_copy activate --cid <CID> --target-parent "/srv/ester"

  # 3) Sobrat i srazu razoslat na targety
  python -m scripts.self_copy build --push --targets t_local t_s3
"""

from __future__ import annotations

import argparse
import json
import os
from typing import List

from modules.selfmanage.archive import build_archive
from modules.selfmanage.manifest import _persist_dir as _persist_dir_fn
from modules.selfmanage.release_registry import ReleaseRegistry
from modules.selfmanage.relocator import execute, plan_activate, rollback
from modules.storage.targets import get_target, list_targets
from modules.storage.uploader import upload_file
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _repo_root() -> str:
    # berem rabochuyu direktoriyu protsessa kak koren repozitoriya
    return os.path.abspath(os.getcwd())


def _policy_from_args(args) -> dict:
    allow = args.policy_allow or []
    return {"allow_move_into": allow, "require_token": bool(args.require_token)}


def _local_archives_dir() -> str:
    base = _persist_dir_fn()
    d = os.path.join(base, "self", "archives")
    os.makedirs(d, exist_ok=True)
    return d


def _enabled_targets(ids: List[str] | None):
    if ids:
        return [t for t in (get_target(tid) for tid in ids) if t and t.get("enabled", True)]
    return [t for t in list_targets(include_disabled=False) if t.get("enabled", True)]


def cmd_build(a) -> int:
    roots = [
        (_repo_root(), "repo"),
        (os.getenv("PERSIST_DIR") or os.path.abspath("./data"), "data"),
    ]
    policy = _policy_from_args(a)
    res = build_archive(roots=roots, policy=policy, secret=os.getenv("ESTER_SELF_SECRET"))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if not res.get("ok"):
        return 2

    # Zapishem reliz v KG i mesto khraneniya (lokalnyy arkhivnyy put)
    cid = res["cid"]
    try:
        rr = ReleaseRegistry()
        rr.record_release(cid)
        rr.record_storage(cid, _local_archives_dir(), kind="local")
    except Exception:
        pass

    # Po zhelaniyu — pushim na targety
    if a.push:
        targets = _enabled_targets(a.targets)
        arc = res["path"]
        summary = []
        for t in targets:
            up = upload_file(t, arc, None)
            summary.append({"target": t["id"], **up})
            # Zafiksiruem v KG khranenie po URL/puti
            try:
                url = (
                    up.get("url")
                    or t.get("config", {}).get("path")
                    or t.get("config", {}).get("bucket")
                )
                if url:
                    ReleaseRegistry().record_storage(cid, str(url), kind=t["type"])
            except Exception:
                pass
        print(json.dumps({"push_results": summary}, ensure_ascii=False, indent=2))
    return 0


def cmd_activate(a) -> int:
    plan = plan_activate(cid=a.cid, target_parent=a.target_parent)
    if not plan.get("ok"):
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 2
    res = execute(plan)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    # KG zapis aktivatsii
    try:
        ReleaseRegistry().record_activation(a.cid)
    except Exception:
        pass
    return 0 if res.get("ok") else 2


def cmd_rollback(a) -> int:
    res = rollback()
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 2


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Ester self-copy tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("build", help="Sobrat arkhiv samosokhraneniya")
    p_b.add_argument(
        "--policy-allow",
        action="append",
        help="Razreshit perenos v etot koren (mozhno neskolko)",
    )
    p_b.add_argument(
        "--require-token",
        action="store_true",
        default=True,
        help="Trebovat ESTER_MOVE_TOKEN pri perenose",
    )
    p_b.add_argument(
        "--push",
        action="store_true",
        help="Posle sborki otpravit arkhiv na targety",
    )
    p_b.add_argument(
        "--targets",
        nargs="*",
        help="Spisok id targetov (po umolchaniyu — vse enabled)",
    )
    p_b.set_defaults(func=cmd_build)

    p_a = sub.add_parser(
        "activate", help="Atomarno pereklyuchitsya na reliz po CID"
    )
    p_a.add_argument("--cid", required=True, help="Identifikator arkhiva (CID)")
    p_a.add_argument(
        "--target-parent",
        required=True,
        help="Katalog, vnutri kotorogo budet releases/<cid>",
    )
    p_a.set_defaults(func=cmd_activate)

    p_r = sub.add_parser(
        "rollback", help="Otkatit posledniy switch current->previous"
    )
    p_r.set_defaults(func=cmd_rollback)

    args = p.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())