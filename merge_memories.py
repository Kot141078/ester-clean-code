# -*- coding: utf-8 -*-
"""merge_memories.py - utilita sliyaniya dvukh JSON-faylov pamyati.

Fixes:
  expected an indented block after 'if' statement
V iskhodnike block:
  if __name__ == "__main__":
byl bez tela (main zakommentirovan), iz-za chego fayl ne kompilirovalsya.

What improved:
- Normalnaya CLI: dry-run, otchet, vybor klyucha deduplikatsii.
- Deduplikatsiya po 'id' (po umolchaniyu) or po vychislyaemomu fingerprint (query+answer/text/message).
- Optionalno: generatsiya id dlya zapisey bez id (--generate-missing-id).
- Atomarnaya zapis rezultata (*.tmp → replace).
- Bolshe validatsii vkhodnykh dannykh: myagko propuskaem musor, no ne padaem.

Mosty (demand):
- Yavnyy most: merge memories → edinyy kanonicheskiy ester_memory.json → ustoychivyy kontekst (SER/EWCEP).
- Skrytye mosty:
  1) Infoteoriya ↔ praktika: fingerprint kak kompaktnaya “signatura soobscheniya” dlya deduplikatsii (szhatie/kanal proverki).
  2) Inzheneriya ↔ ekspluatatsiya: atomarnaya zapis + dry-run = predokhranitel ot porchi dannykh.

ZEMNOY ABZATs: v kontse fayla."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

JSONDict = Dict[str, Any]
Entry = Dict[str, Any]


def load_json(path: str) -> JSONDict:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at top-level, got: {type(data).__name__}")
    return data


def save_json_atomic(path: str, data: JSONDict) -> None:
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def fingerprint_entry(e: Entry) -> str:
    """Fingerprint dlya deduplikatsii, esli id ​​otsutstvuet.

    Stabilnyy i korotkiy: sha256 → pervye 8 bayt hex."""
    parts = [
        _safe_str(e.get("query")),
        _safe_str(e.get("answer")),
        _safe_str(e.get("text")),
        _safe_str(e.get("message")),
        _safe_str(e.get("kind")),
    ]
    blob = "\n".join(p for p in parts if p).encode("utf-8", errors="replace")
    h = hashlib.sha256(blob).digest()
    return h[:8].hex()


def as_map(entries: List[Entry], key: str) -> Dict[str, Entry]:
    out: Dict[str, Entry] = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        v = e.get(key)
        if v:
            out[str(v)] = e
    return out


def _iter_users(mem: JSONDict) -> Iterable[Tuple[str, List[Entry]]]:
    # Ozhidaem strukturu: { user: [ {id, query, answer, ...}, ... ] }
    for user, lst in (mem or {}).items():
        if isinstance(user, str) and isinstance(lst, list):
            yield user, lst


def merge(
    primary_path: str,
    secondary_path: str,
    *,
    dedupe_key: str = "id",          # "id" | "fp"
    generate_missing_id: bool = False,
    dry_run: bool = False,
) -> int:
    primary = load_json(primary_path)
    secondary = load_json(secondary_path)

    total_added = 0
    total_seen = 0
    total_skipped = 0
    total_fixed_ids = 0

    for user, s_list in _iter_users(secondary):
        p_list = primary.setdefault(user, [])
        if not isinstance(p_list, list):
            p_list = []
            primary[user] = p_list

        if dedupe_key == "id":
            p_map = as_map(p_list, "id")
        else:
            p_map = {fingerprint_entry(e): e for e in p_list if isinstance(e, dict)}

        added = 0
        skipped = 0
        fixed_ids = 0

        for e in s_list:
            total_seen += 1
            if not isinstance(e, dict):
                skipped += 1
                continue

            if generate_missing_id and not e.get("id"):
                e["id"] = uuid.uuid4().hex
                fixed_ids += 1

            if dedupe_key == "id":
                key_val = _safe_str(e.get("id")) or None
                if not key_val:
                    # if there is no ID, use FP to avoid creating duplicates
                    key_val = fingerprint_entry(e)
            else:
                key_val = fingerprint_entry(e)

            if not key_val:
                skipped += 1
                continue

            if key_val in p_map:
                skipped += 1
                continue

            p_list.append(e)
            p_map[key_val] = e
            added += 1

        total_added += added
        total_skipped += skipped
        total_fixed_ids += fixed_ids
        print(f"[{user}] added={added}, skipped={skipped}, fixed_ids={fixed_ids}, total={len(p_list)}")

    print(f"[TOTAL] seen={total_seen}, added={total_added}, skipped={total_skipped}, fixed_ids={total_fixed_ids}")

    if dry_run:
        print("[DRY-RUN] no changes written.")
        return 0

    save_json_atomic(primary_path, primary)
    print("[OK] merged into", primary_path)
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Merge two Ester memory JSON files (per-user lists).")
    ap.add_argument(
        "--primary",
        required=True,
        help="Where is Merjim (canonical ester_memory.zhsion).",
    )
    ap.add_argument(
        "--secondary",
        required=True,
        help="Otkuda dokinut zapisi (legacy / drugoy uzel).",
    )
    ap.add_argument(
        "--dedupe-key",
        choices=["id", "fp"],
        default="id",
        help="Deduplication key: id (default) or fp (fingerprint).",
    )
    ap.add_argument(
        "--generate-missing-id",
        action="store_true",
        help="Generate id for records where there is no id (ooid4 hex).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the report, but do not record the result.",
    )
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    dk = "id" if args.dedupe_key == "id" else "fp"
    return merge(
        args.primary,
        args.secondary,
        dedupe_key=dk,
        generate_missing_id=bool(args.generate_missing_id),
        dry_run=bool(args.dry_run),
    )


if __name__ == "__main__":
    raise SystemExit(main())


ZEMNOY = """ZEMNOY ABZATs (anatomiya/inzheneriya):
Sliyanie pamyati - kak perelivanie krovi mezhdu dvumya sistemami khraneniya: vazhno ne “udvoit” kletki i ne zanesti gryaz.
Inzhenerno eto pokhozhe na skladskuyu inventarizatsiyu: esli net unikalnogo nomera detail (id), berem otpechatok (fp)
po soderzhimomu, chtoby ne zavezti vtoroy raz tot zhe yaschik. Atomarnaya zapis - kak plomba na vorotakh: libo vse
obnovilos tselikom, libo nichego ne tronuli."""