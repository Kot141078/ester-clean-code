# tools/salvage_memory_json.py
# -*- coding: utf-8 -*-
"""
Salvage tool for Ester memory snapshot.

Fishka etoy versii:
- utf-8-sig: sedaet BOM
- umeet startovat NE tolko s '{', no i s '"' (esli fayl poteryal vneshnyuyu skobku)
- esli v nachale musor/obrezka — ischet pervyy '{' ili '"' dalshe po potoku
- vytaskivaet pary key->value do mesta porchi i pishet validnyy JSON-obekt

Mosty (trebovanie artefakta):
- YaVNYY: kibernetika (Eshbi: ustoychivost kontura) ↔ inzheneriya FS (atomarnost zapisi/zameny)
- SKRYTYY #1: logika (Enderton): nezakrytaya konstruktsiya ⇒ net interpretatsii ⇒ obrezaem do poslednego korrektnogo fragmenta
- SKRYTYY #2: infoteoriya (Cover&Thomas): rost “obema/entropii” snapshota povyshaet shans chastichnoy zapisi pri sboe

Zemnoy abzats:
Eto kak shov na sosude: esli ego “ne dotyanuli” ili porvali pri perenose, davlenie prevraschaet strukturu v kashu.
Lechim: snachala obrezaem do zhivogo (salvage), potom fiksiruem tekhniku “shva” (atomarnaya zapis ryadom + replace).

c=a+b
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from typing import Dict, Any, Optional, TextIO, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def resolve_state_root() -> str:
    st = (os.environ.get("ESTER_STATE_DIR") or os.environ.get("ESTER_HOME") or "").strip()
    if not st:
        st = (os.environ.get("ESTER_ROOT") or os.getcwd()).strip()
    return st


def default_memory_path(state_root: str) -> str:
    return os.path.join(state_root, "data", "memory", "memory.json")


def find_best_input(mem_path: str) -> str:
    pattern = mem_path + ".corrupt_*"
    candidates = glob.glob(pattern)
    if candidates:
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]
    return mem_path


def is_valid_json_dict(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            obj = json.load(f)
        return isinstance(obj, dict)
    except Exception:
        return False


def _read_more(f: TextIO, buf: str, chunk_size: int) -> Tuple[str, bool]:
    chunk = f.read(chunk_size)
    if not chunk:
        return buf, True
    return buf + chunk, False


def _skip_ws_and_bom(buf: str, i: int) -> int:
    n = len(buf)
    while i < n and (buf[i] in " \t\r\n" or buf[i] == "\ufeff"):
        i += 1
    return i


def _seek_first_struct_char(buf: str, start: int) -> Optional[int]:
    """
    Find earliest occurrence of '{' or '"' after 'start'. Return index or None.
    """
    pos_obj = buf.find("{", start)
    pos_key = buf.find('"', start)
    candidates = [p for p in (pos_obj, pos_key) if p != -1]
    return min(candidates) if candidates else None


def salvage_pairs_like_object(input_path: str, output_path: str, chunk_size: int = 1024 * 1024) -> Tuple[int, str]:
    """
    Salvage top-level key/value pairs from:
    - a JSON object: { "k": v, ... }
    - or a “headless” object content: "k": v, "k2": v2, ...

    Returns: (recovered_count, mode)
      mode: "object" | "headless"
    """
    dec = json.JSONDecoder()
    recovered = 0
    first_written = False

    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    tmp_out = output_path + ".tmp"

    with open(input_path, "r", encoding="utf-8-sig", errors="ignore") as f, open(tmp_out, "w", encoding="utf-8") as out:
        buf = ""
        eof = False
        i = 0

        buf, eof = _read_more(f, buf, chunk_size)
        i = _skip_ws_and_bom(buf, i)
        if i >= len(buf) and eof:
            raise RuntimeError("Empty input.")

        # Determine start mode
        mode = None  # "object" or "headless"
        while mode is None:
            i = _skip_ws_and_bom(buf, i)
            if i >= len(buf):
                if eof:
                    break
                buf, eof = _read_more(f, buf, chunk_size)
                continue

            ch = buf[i]
            if ch == "{":
                mode = "object"
                i += 1
                break
            if ch == '"':
                mode = "headless"
                break

            # seek forward for '{' or '"'
            j = _seek_first_struct_char(buf, i)
            if j is not None:
                i = j
                continue

            if eof:
                break
            buf, eof = _read_more(f, buf, chunk_size)

        if mode is None:
            raise RuntimeError("Cannot find start of JSON object or key string in input.")

        out.write("{")

        # Main loop: parse key -> ":" -> value, separated by commas
        while True:
            i = _skip_ws_and_bom(buf, i)

            # refill if needed
            if i >= len(buf) and not eof:
                buf, eof = _read_more(f, buf, chunk_size)
                continue

            if i >= len(buf) and eof:
                break

            # If we are in real object mode and see closing brace — done
            if mode == "object":
                if i < len(buf) and buf[i] == "}":
                    i += 1
                    break

            # Optional leading comma (some corrupt cases)
            if i < len(buf) and buf[i] == ",":
                i += 1
                continue

            # Expect key string
            key = None
            while True:
                try:
                    key, j = dec.raw_decode(buf, i)
                    if not isinstance(key, str):
                        # Not a key => stop salvage safely
                        key = None
                    else:
                        i = j
                    break
                except json.JSONDecodeError as e:
                    # if near end and not eof -> read more
                    if (not eof) and (e.pos >= len(buf) - 64):
                        buf, eof = _read_more(f, buf, chunk_size)
                        continue
                    key = None
                    break

            if key is None:
                break

            i = _skip_ws_and_bom(buf, i)

            # Need colon
            if i >= len(buf) and not eof:
                buf, eof = _read_more(f, buf, chunk_size)
                i = _skip_ws_and_bom(buf, i)

            if i >= len(buf) or buf[i] != ":":
                break
            i += 1
            i = _skip_ws_and_bom(buf, i)

            # Parse value
            val = None
            while True:
                try:
                    val, j = dec.raw_decode(buf, i)
                    i = j
                    break
                except json.JSONDecodeError as e:
                    if (not eof) and (e.pos >= len(buf) - 64):
                        buf, eof = _read_more(f, buf, chunk_size)
                        continue
                    val = None
                    break

            if val is None:
                break

            # write recovered pair
            if first_written:
                out.write(",")
            else:
                first_written = True

            out.write(json.dumps(key, ensure_ascii=False))
            out.write(":")
            out.write(json.dumps(val, ensure_ascii=False))
            recovered += 1

            # Skip trailing spaces/comma; in object mode we may see '}'.
            i = _skip_ws_and_bom(buf, i)

            if i >= len(buf) and not eof:
                buf, eof = _read_more(f, buf, chunk_size)
                i = _skip_ws_and_bom(buf, i)

            if i < len(buf) and buf[i] == ",":
                i += 1
                continue

            if mode == "object" and i < len(buf) and buf[i] == "}":
                i += 1
                break

            # In headless mode we stop only on failure; otherwise loop continues

        out.write("}")

    os.replace(tmp_out, output_path)
    return recovered, mode


def backup_file(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    stamp = time.strftime("%Y%m%d_%H%M%S")
    bak = f"{path}.bak_{stamp}"
    with open(path, "rb") as src, open(bak, "wb") as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)
    return bak


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="", help="Path to memory.json or memory.json.corrupt_*")
    ap.add_argument("--apply", action="store_true", help="Replace memory.json with salvaged (with backup).")
    ap.add_argument("--chunk", type=int, default=1024 * 1024, help="Read chunk size (bytes).")
    args = ap.parse_args()

    state = resolve_state_root()
    mem_path = default_memory_path(state)
    input_path = args.input.strip() or find_best_input(mem_path)

    if not os.path.exists(input_path):
        print(f"[ERR] input not found: {input_path}")
        return 2

    # If already valid dict — nothing to salvage
    if is_valid_json_dict(input_path):
        print(f"[OK] Input is already valid JSON dict: {input_path}")
        if args.apply and os.path.abspath(input_path) != os.path.abspath(mem_path):
            bak = backup_file(mem_path)
            if bak:
                print(f"[OK] backup: {bak}")
            os.makedirs(os.path.dirname(mem_path), exist_ok=True)
            os.replace(input_path, mem_path)
            print(f"[OK] applied: {mem_path}")
        return 0

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(os.path.dirname(mem_path), f"memory.json.salvaged_{stamp}")

    print(f"[INFO] state_root: {state}")
    print(f"[INFO] mem_path  : {mem_path}")
    print(f"[INFO] input     : {input_path}")
    print(f"[INFO] output    : {out_path}")

    recovered, mode = salvage_pairs_like_object(input_path, out_path, chunk_size=args.chunk)
    print(f"[OK] mode={mode} recovered={recovered}")

    if not is_valid_json_dict(out_path):
        print("[ERR] Salvaged output is not a valid JSON dict (unexpected).")
        return 1

    print("[OK] Salvaged output validated as JSON dict.")

    if args.apply:
        bak = backup_file(mem_path)
        if bak:
            print(f"[OK] backup: {bak}")
        os.makedirs(os.path.dirname(mem_path), exist_ok=True)
        os.replace(out_path, mem_path)
        print(f"[OK] applied: {mem_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())