# -*- coding: utf-8 -*-
"""scripts/usb_deploy_release.py - universalnyy deploy relizov i dampov na/s USB dlya Ester.

Vyzov:
  python -m scripts.usb_deploy_release --direction to-usb|--from-usb --mount /path/to/mount [--archive file.zip] [--dump file.tar.gz]

Stsenarii:
  - to-usb: Zapisyvaet reliz v /ESTER/releases/<cid>.zip or damp v /ESTER/dumps/<file>, addavlyaet bootstrap-skript.
  - from-usb: Kopiruet release v ~/.ester/releases/<ts>/ or damp v ~/.ester/inbox/projects/, ispolzuet manifest.json or avto-poisk.

Mosty:
- Yavnyy (Kibernetika ↔ Ekspluatatsiya): atomarnyy perenos faylov v obe sidery.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): strict JSON-otchet s polem strategy.
- Skrytyy 2 (Praktika ↔ Bezopasnost): nikakikh vmeshatelstv v servisy, tolko faylovye operatsii.

Zemnoy abzats:
Kak zabotlivyy medbrat: akkuratno perekladyvaet pakety v nuzhnye shkafchiki (na USB or s USB), ostavlyaet zapisku (JSON), nichego ne lomaet."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from modules.selfmanage.usb_locator import (  # Iz originala
    find_or_prepare_usb,
    prepare_ester_folder,
)

USB_LABEL = os.getenv("ESTER_USB_LABEL", "ESTER").strip() or "ESTER"
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))

_BOOTSTRAP_PY = """#!/usr/bin/env python3
# USB bootstrap - launched manually from USB: collects Esther from a dump on the current machine.
import os, sys, json
from modules.selfmanage.dump_assembler import assemble_from_archive
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main():
    if len(sys.argv) < 2:
        print("Usage: python usb_bootstrap.py <archive_path> [target_parent]")
        return 2
    arc = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) >= 3 else (os.getenv("ESTER_RUN_ROOT") or os.getcwd())
    res = assemble_from_archive(arc, target_parent=target, require_token=False)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 2

if __name__ == "__main__":
    raise SystemExit(main())"""


def _copy(src: Path, dst: Path) -> Dict:
    """Copies the file and returns information for the report."""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        return {
            "src": str(src),
            "dst": str(dst),
            "bytes": int(dst.stat().st_size) if dst.exists() else 0,
        }
    except (PermissionError, OSError) as e:
        return {"src": str(src), "dst": str(dst), "error": f"copy-failed: {str(e)}"}


def _find_release_zip(ester_dir: Path) -> Optional[Path]:
    """Searches the release archive using templates."""
    for pat in ("releases/*.zip", "releases/*.tar.gz", "ester_release.tar.gz", "ester_release.zip"):
        for p in ester_dir.glob(pat):
            return p
    return None


def _read_manifest(ester_dir: Path) -> Optional[Dict]:
    """Chitaet manifest.json s USB."""
    mf = ester_dir / "manifest.json"
    if not mf.exists():
        return None
    try:
        return json.loads(mf.read_text(encoding="utf-8"))
    except Exception:
        return None


def _manifest_pick(ester_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """Izvlekaet puti k relizu i dampu iz manifest.json."""
    m = _read_manifest(ester_dir)
    rel, dump = None, None
    if m and isinstance(m.get("items"), list):
        for it in m["items"]:
            path = it.get("path")
            kind = it.get("kind")
            if not path or not kind:
                continue
            p = (ester_dir.parent / path) if not path.startswith("/") else Path(path)
            if kind == "release" and p.exists():
                rel = p
            if kind == "dump" and p.exists():
                dump = p
    return rel, dump


def _extract_cid_from_archive(arc: Path) -> Optional[str]:
    """Retrieves the CID from the archive if there is a manifest.zhsion."""
    try:
        if zipfile.is_zipfile(arc):
            with zipfile.ZipFile(arc, "r") as z:
                if "manifest.json" in z.namelist():
                    man = json.loads(z.read("manifest.json").decode("utf-8"))
                    return man.get("cid")
    except Exception:
        pass
    return None


def main(argv: list[str] | None = None) -> int:
    """Basic logic of deployment to/from USB."""
    ap = argparse.ArgumentParser(description="Ester USB Deploy Release")
    ap.add_argument(
        "--direction",
        choices=["to-usb", "from-usb"],
        required=True,
        help="Napravlenie: na USB ili s USB",
    )
    ap.add_argument(
        "--mount",
        default=None,
        help="USB mount point (for to-usb: if not specified - auto)",
    )
    ap.add_argument(
        "--archive",
        default="",
        help="Path to the release archive (if empty, try manifest/auto)",
    )
    ap.add_argument(
        "--dump",
        default="",
        help="Path to dump (if empty, try manifest/auto)",
    )
    args = ap.parse_args(argv)

    report: Dict = {
        "ok": True,
        "ester_dir": None,
        "copied": [],
        "source": {"archive": None, "dump": None},
        "strategy": "args",
    }

    # Opredelyaem koren USB
    usb_root = None
    if args.direction == "to-usb":
        if args.mount:
            usb_root = prepare_ester_folder(args.mount)
        else:
            usb_root = find_or_prepare_usb(require_sentinel=False)
        if not usb_root:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "no-suitable-usb",
                        "details": "Prepare or set ESTER_USB_ALLOWLIST",
                    },
                    ensure_ascii=False,
                )
            )
            return 2
    else:
        usb_root = Path(args.mount).resolve() / USB_LABEL
        if not usb_root.exists():
            print(
                json.dumps(
                    {"ok": False, "error": "ester-dir-not-found", "path": str(usb_root)},
                    ensure_ascii=False,
                )
            )
            return 2

    report["ester_dir"] = str(usb_root)

    # Vybor istochnikov
    arch = Path(args.archive).resolve() if args.archive else None
    dmp = Path(args.dump).resolve() if args.dump else None
    if (not arch or not arch.exists() or args.archive == "") or (
        not dmp or not dmp.exists() or args.dump == ""
    ):
        m_rel, m_dump = _manifest_pick(usb_root)
        if m_rel and args.direction == "from-usb":
            arch = arch or m_rel
            report["strategy"] = "manifest"
        if m_dump and args.direction == "from-usb":
            dmp = dmp or m_dump
            report["strategy"] = "manifest"
        if (
            (not arch or not arch.exists())
            and args.direction == "from-usb"
            and report["strategy"] != "manifest"
        ):
            arch = _find_release_zip(usb_root)
            report["strategy"] = "auto" if arch else report["strategy"]

    report["source"]["archive"] = str(arch) if arch else None
    report["source"]["dump"] = str(dmp) if dmp else None

    # Kopirovanie
    if args.direction == "to-usb":
        rel_dir = usb_root / "releases"
        dump_dir = usb_root / "dumps"
        boot_dir = usb_root / "bootstrap"
        os.makedirs(rel_dir, exist_ok=True)
        os.makedirs(dump_dir, exist_ok=True)
        os.makedirs(boot_dir, exist_ok=True)

        if arch and arch.exists():
            cid = _extract_cid_from_archive(arch) or arch.stem
            dst = rel_dir / f"{cid}.zip"
            report["copied"].append(_copy(arch, dst))
            # Sozdaem manifest.json
            manifest = {
                "items": [{"path": str(dst.relative_to(usb_root.parent)), "kind": "release"}]
            }
            (usb_root / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            # Bootstrap-skript
            (boot_dir / "usb_bootstrap.py").write_text(_BOOTSTRAP_PY, encoding="utf-8")

        if dmp and dmp.exists():
            dst = dump_dir / dmp.name
            report["copied"].append(_copy(dmp, dst))
            # Update manifest.jsion
            manifest = _read_manifest(usb_root) or {"items": []}
            manifest["items"].append(
                {"path": str(dst.relative_to(usb_root.parent)), "kind": "dump"}
            )
            (usb_root / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            # Bootstrap-skript
            (boot_dir / "usb_bootstrap.py").write_text(_BOOTSTRAP_PY, encoding="utf-8")

    else:  # from-usb
        if dmp and dmp.exists():
            dst_dump = STATE_DIR / "inbox" / "projects" / dmp.name
            report["copied"].append(_copy(dmp, dst_dump))
        if arch and arch.exists():
            ts = int(time.time())
            dst_archive = STATE_DIR / "releases" / str(ts) / arch.name
            report["copied"].append(_copy(arch, dst_archive))
            note = dst_archive.with_suffix(".note.json")
            note.write_text(
                json.dumps(
                    {
                        "ts": ts,
                        "src": str(arch),
                        "dst": str(dst_archive),
                        "info": "a copy of the release archive; unpacking/pickup - outside of this command",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["copied"] or not (arch or dmp) else 2


if __name__ == "__main__":
    raise SystemExit(main())