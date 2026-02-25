# -*- coding: utf-8 -*-
from __future__ import annotations

"""restore_from_dump.py

Vosstanavlivaet proekt iz chastey (Ester_dump_part_*.txt) po manifestu ester_manifest.json.
Sozdaet fayly/katalogi zanovo, dekodiruet binarniki iz base64.

Zapusk (primer):
    python restore_from_dump.py --out "D:\ester-project_restored"

Optsii:
  --manifest PATH put k ester_manifest.json (po umolchaniyu ./ester_manifest.json)
  --parts-dir DIR where lezhat Ester_dump_part_*.txt (po umolchaniyu ryadom s manifest)
  --verify-only tolko proverka SHA256 (bez raspakovki)
  --strict pri otsutstvii chasti/fayla — schitat oshibkoy (i vernut nenulevoy kod)

Mosty:
- Yavnyy: manifest (struktura) → vosstanovlenie faylov (realnost).
- Skrytye:
  1) Infoteoriya ↔ nadezhnost: verify (SHA256) = proverka tselostnosti kanala.
  2) Inzheneriya ↔ ekspluatatsiya: potokovyy razbor chastey → ne derzhim gigabayty v pamyati.

ZEMNOY ABZATs: vnizu fayla."""

import argparse
import base64
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


MANIFEST_DEFAULT = "ester_manifest.json"
PART_NAME_RE = re.compile(r"^Ester_dump_part_\d{4}\.txt$")

BEGIN_RE = re.compile(r"^----- BEGIN FILE: (.+?)\s+\(size=(\d+)\s+B,")
END_RE = re.compile(r"^----- END FILE: (.+?) -----\s*$")
B64_START = "[BINARY BASE64 DATA START]"
B64_END = "[BINARY BASE64 DATA END]"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_manifest(manifest_path: Path) -> Dict:
    with manifest_path.open("r", encoding="utf-8") as mf:
        return json.load(mf)


def _resolve_parts_dir(manifest_path: Path, parts_dir: Optional[str]) -> Path:
    if parts_dir:
        return Path(parts_dir).resolve()
    return manifest_path.parent.resolve()


def _iter_part_lines(part_path: Path) -> Iterable[str]:
    # Important: stream (not redlines), so as not to load memory.
    with part_path.open("r", encoding="utf-8") as pf:
        for line in pf:
            yield line.rstrip("\n")


def _restore_one_part(
    out_root: Path,
    part_path: Path,
    wanted_relpaths: Optional[set],
    *,
    strict: bool,
) -> Tuple[int, int]:
    """
    Vosstanavlivaet fayly iz odnoy chasti.
    Vozvraschaet (restored_count, skipped_count).
    """
    restored = 0
    skipped = 0

    it = iter(_iter_part_lines(part_path))
    for line in it:
        m = BEGIN_RE.match(line)
        if not m:
            continue

        relpath = m.group(1).strip()
        # if we have a vnitlist and the file is not needed, we skip the block to the END
        need = True
        if wanted_relpaths is not None:
            need = relpath in wanted_relpaths

        is_binary = False
        b64_mode = False
        buf_text: List[str] = []
        buf_b64: List[str] = []

        for inner in it:
            if inner == B64_START:
                is_binary = True
                b64_mode = True
                continue
            if inner == B64_END:
                b64_mode = False
                continue

            me = END_RE.match(inner)
            if me and me.group(1).strip() == relpath:
                # konets bloka
                if not need:
                    skipped += 1
                    break

                out_path = out_root / Path(relpath.replace("/", os.sep))
                ensure_parent_dir(out_path)

                try:
                    if is_binary:
                        raw = base64.b64decode("".join(buf_b64))
                        out_path.write_bytes(raw)
                    else:
                        # normalizuem newlines
                        out_path.write_text("\n".join(buf_text) + "\n", encoding="utf-8", newline="\n")
                    restored += 1
                except Exception as ex:
                    msg = f"[ERR ] write failed: {relpath} :: {ex}"
                    if strict:
                        raise RuntimeError(msg) from ex
                    print(msg)
                break

            # nakoplenie
            if b64_mode:
                if inner and not inner.startswith("[READ ERROR"):
                    buf_b64.append(inner)
            else:
                buf_text.append(inner)

    return restored, skipped


def verify_sha256(out_root: Path, manifest: Dict, *, strict: bool) -> int:
    print("YuHKshch I'm checking SHA256...")
    bad = 0
    entries = manifest.get("entries") or []
    for e in entries:
        rp = e.get("relpath") or ""
        exp = e.get("sha256")
        if not rp or not exp:
            continue
        path = out_root / Path(rp.replace("/", os.sep))
        if not path.exists():
            print(f"[MISS] {rp}")
            bad += 1
            if strict:
                continue
            continue
        try:
            act = sha256_file(path)
            if act != exp:
                print(f"[FAIL] {rp}: sha256 mismatch")
                bad += 1
        except Exception as ex:
            print(f"[ERR ] {rp}: {ex}")
            bad += 1

    if bad == 0:
        print("yOKshch Recovery completed without hash discrepancies")
    else:
        print(f"YuVARNsch Mismatches/errors: ZZF0Z")
    return bad


def restore(out_root: Path, manifest_path: Path, parts_dir: Path, *, strict: bool) -> None:
    manifest = _load_manifest(manifest_path)

    # parts: list of parts file names (as in manifest)
    parts = [p.get("name") for p in (manifest.get("parts") or [])]
    parts = [x for x in parts if isinstance(x, str) and x.strip()]
    part_map: Dict[int, str] = {i + 1: parts[i] for i in range(len(parts))}

    # entries grouped by part
    entries_by_part: Dict[int, List[Dict]] = {}
    for e in (manifest.get("entries") or []):
        try:
            entries_by_part.setdefault(int(e.get("part")), []).append(e)
        except Exception:
            continue

    # parse each part
    total_restored = 0
    total_skipped = 0
    for part_idx, items in sorted(entries_by_part.items()):
        part_name = part_map.get(part_idx)
        if not part_name:
            msg = f"YuVARNsch No part file name for index ZZF0Z"
            if strict:
                raise RuntimeError(msg)
            print(msg)
            continue

        part_path = (parts_dir / part_name).resolve()
        if not part_path.exists():
            msg = f"[WARN] Net fayla chasti: {part_path}"
            if strict:
                raise FileNotFoundError(msg)
            print(msg)
            continue

        wanted = {str(x.get("relpath")) for x in items if x.get("relpath")}
        print(f"[PART] Razbor {part_path.name} ({len(wanted)} faylov v manifeste)")
        r, s = _restore_one_part(out_root, part_path, wanted, strict=strict)
        total_restored += r
        total_skipped += s

    print(f"[DONE] restored={total_restored}, skipped={total_skipped}")

    # verify
    bad = verify_sha256(out_root, manifest, strict=strict)
    if bad and strict:
        raise RuntimeError(f"verify failed: bad={bad}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Vosstanovlenie proekta iz Ester_dump_part_*.txt")
    ap.add_argument("--out", required=True, help="Kuda razvernut vosstanovlennyy proekt")
    ap.add_argument("--manifest", default=MANIFEST_DEFAULT, help="Put k ester_manifest.json (po umolchaniyu ./ester_manifest.json)")
    ap.add_argument("--parts-dir", default="", help="Folder with Esther_dump_part_*.txt (next to manifest by default)")
    ap.add_argument("--verify-only", action="store_true", help="Only checking ША256 (without unpacking)")
    ap.add_argument("--strict", action="store_true", help="Treat missing/errors as fatal (non-zero code)")

    args = ap.parse_args(argv)

    out_root = Path(args.out).resolve()
    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"[ERR ] manifest not found: {manifest_path}")
        return 2

    parts_dir = _resolve_parts_dir(manifest_path, args.parts_dir if args.parts_dir else None)
    if not parts_dir.exists():
        print(f"[ERR ] parts dir not found: {parts_dir}")
        return 2

    out_root.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(manifest_path)

    if args.verify_only:
        bad = verify_sha256(out_root, manifest, strict=bool(args.strict))
        return 0 if bad == 0 else 3

    try:
        restore(out_root, manifest_path, parts_dir, strict=bool(args.strict))
        return 0
    except Exception as ex:
        print(f"[ERR ] {ex}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())


ZEMNOY = """ZEMNOY ABZATs (anatomiya/inzheneriya):
Vosstanovlenie iz dampa - eto kak sobrat organizm po tkanyam i sverit DNK.
Sami fayly - “plot”, manifest - “skhema sborki”, and SHA256 - kontrol, what nichego ne podmenili i ne porvali po doroge.
Esli kontrol propustit - mozhno poluchit “pokhozhiy” project, no s polomannymi nervami."""