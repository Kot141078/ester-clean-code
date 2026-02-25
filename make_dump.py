# -*- coding: utf-8 -*-
"""make_dump.py
Sobiraet project v nabor udobnykh "tomov" (chastey) po zadannomu razmeru.

Rezhimy:
  source - vklyuchaet tolko iskhodniki/teksty/konfigi/shablony
  full - vklyuchaet vse (vklyuchaya binarnye, v base64)

Generate:
  ester_manifest.json - manifest so spiskom faylov, razmerami, SHA256 i nomerom chasti
  Ester_dump_part_0001.txt, Ester_dump_part_0002.txt, ...

Kazhdaya chast ≤ --part-size megabayt (by default 5 MB).

A/B-sloty (recommendations for bezopasnoy zamene):
  A = tekuschiy fayl; B = rezervnaya kopiya do izmeneniya (for example, make_dump.py.bak).
  V sluchae sboev - otkatitsya na B.

Mosty:
  - Yavnyy: (Kibernetika ↔ Arkhitektura) - limit razmera kak regulyator stabilnosti.
  - Skrytye: (Infoteoriya ↔ Kanaly) — part_size kak kontrol propusknoy sposobnosti.
  - Skrytye: (Anatomiya ↔ Inzheneriya) - “kapillyarizatsiya” bolshikh dampov na melkie toma.

Zemnoy abzats:
  Kladi script v koren proekta. Zapusk:
      python make_dump.py --mode source --output-dir D:\ester-dump
      python make_dump.py --mode full --part-size 5 --output-dir D:\ester-dump
  Vykhod: chasti po ≤5 MB, manifest s kontrolnymi summami.

# c=a+b"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

# === Izmenenie: defolt teper 5 MB ===
DEFAULT_PART_MB = 2

PART_NAME = "Ester_dump_part_{:04d}.txt"
MANIFEST = "ester_manifest.json"

SOURCE_TEXT_EXTS = {
    ".py",
    "",
    ".md",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".toml",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".vue",
    ".csv",
    ".bat",
    ".ps1",
    ".sh",
    ".env",
    ".jinja",
    ".jinja2",
}

# In Source mode, excludes heavy directories by default
DEFAULT_EXCLUDE_DIRS_SOURCE = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    ".idea",
    ".vscode",
    ".DS_Store",
}


def rel(path: str) -> str:
    return os.path.relpath(path, PROJECT_ROOT).replace("\\", "/")


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: str, mode: str, exclude_dirs: set | None) -> List[Tuple[str, int]]:
    files: List[Tuple[str, int]] = []
    for base, dirs, flist in os.walk(root):
        if exclude_dirs:
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for name in flist:
            full = os.path.join(base, name)
            # we do not include our own output artifacts
            if (
                os.path.basename(full).startswith("Ester_dump_part_")
                or os.path.basename(full) == MANIFEST
            ):
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if mode == "source":
                ext = os.path.splitext(name)[1].lower()
                if ext in SOURCE_TEXT_EXTS:
                    files.append((full, size))
            else:
                files.append((full, size))
    files.sort(key=lambda x: x[0].lower())
    return files


class PartWriter:
    def __init__(self, part_mb: int, output_dir: str):
        self.limit = part_mb * 1024 * 1024
        self.part_idx = 0
        self.cur_size = 0
        self.out: io.TextIOWrapper | None = None
        self.parts: List[str] = []
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _open_new(self):
        if self.out:
            self.out.close()
        self.part_idx += 1
        name = PART_NAME.format(self.part_idx)
        path = self.output_dir / name
        self.out = io.open(path, "w", encoding="utf-8", newline="\n")
        self.parts.append(name)
        self.cur_size = 0
        self._write_header(name)

    def _write_header(self, name: str):
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        self.write_text(
            f"# Ester — Damp chast {self.part_idx:04d}\n# Sgenerirovano: {created_at}\n# Fayl: {name}\n\n"
        )

    def write_text(self, s: str):
        data = s.encode("utf-8")
        # If there is no file or does not fit, open a new one (if the fragment itself is less than the limit)
        if not self.out or (self.cur_size + len(data) > self.limit and len(data) < self.limit):
            self._open_new()
        if not self.out:
            self._open_new()
        self.out.write(s)
        self.cur_size += len(data)

    def close(self):
        if self.out:
            self.out.close()
            self.out = None


def dump_text_file(pw: PartWriter, path: str, size: int):
    r = rel(path)
    pw.write_text(f"----- BEGIN FILE: {r}  (size={size} B, type=text) -----\n")
    # Bug fix: correctly add the final en if it is not there
    try:
        last_chunk = ""
        with io.open(path, "r", encoding="utf-8") as f:
            for chunk in iter(lambda: f.read(8192), ""):
                pw.write_text(chunk)
                last_chunk = chunk
        if size > 0 and not last_chunk.endswith("\n"):
            pw.write_text("\n")
    except Exception:
        # fallback cp1251
        try:
            last_chunk = ""
            with io.open(path, "r", encoding="cp1251", errors="replace") as f:
                for chunk in iter(lambda: f.read(8192), ""):
                    pw.write_text(chunk)
                    last_chunk = chunk
            if size > 0 and not last_chunk.endswith("\n"):
                pw.write_text("\n")
        except Exception as e:
            pw.write_text(f"[READ ERROR: {e}]\n")
    pw.write_text(f"----- END FILE: {r} -----\n\n")


def dump_binary_file(pw: PartWriter, path: str, size: int):
    r = rel(path)
    pw.write_text(f"----- BEGIN FILE: {r}  (size={size} B, type=binary, encoding=base64) -----\n")
    pw.write_text("[BINARY BASE64 DATA START]\n")
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                b64 = base64.b64encode(chunk).decode("ascii")
                # stroki po 76 simvolov
                for i in range(0, len(b64), 76):
                    pw.write_text(b64[i : i + 76] + "\n")
    except Exception as e:
        pw.write_text(f"[READ ERROR: {e}]\n")
    pw.write_text("[BINARY BASE64 DATA END]\n")
    pw.write_text(f"----- END FILE: {r} -----\n\n")


def is_text_ext(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in SOURCE_TEXT_EXTS


def main():
    ap = argparse.ArgumentParser(description="Ester split dumper")
    ap.add_argument(
        "--mode",
        choices=["source", "full"],
        default="source",
        help="source: sources/texts only; full: everything, including binaries (basier64)",
    )
    ap.add_argument(
        "--part-size",
        type=int,
        default=DEFAULT_PART_MB,
        help="size of one part, MB (default 5)",
    )
    ap.add_argument(
        "--no-exclude",
        action="store_true",
        help="in source mode, do not exclude anything (caution: there will be a lot)",
    )
    ap.add_argument(
        "--output-dir",
        default=".",
        help="directory for dump output (current by default)",
    )
    args = ap.parse_args()

    exclude_dirs = (
        set() if (args.no_exclude or args.mode == "full") else set(DEFAULT_EXCLUDE_DIRS_SOURCE)
    )

    files = iter_files(PROJECT_ROOT, args.mode, exclude_dirs)
    total_sz = sum(sz for _, sz in files)
    manifest: Dict = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "project_root": PROJECT_ROOT,
        "mode": args.mode,
        "part_size_mb": args.part_size,
        "files_total": len(files),
        "bytes_total": total_sz,
        "parts": [],
        "entries": [],
    }

    pw = PartWriter(args.part_size, args.output_dir)
    start = time.time()

    # Tree (we will write it in the first part automatically)
    pw.write_text("=" * 90 + "\nDEREVO FAYLOV (s razmerami)\n" + "=" * 90 + "\n")
    for p, sz in files:
        pw.write_text(f"{rel(p):<100} {sz:>12} B\n")
    pw.write_text("\n" + "=" * 90 + "\nPOLNOE SODERZhIMOE FAYLOV\n" + "=" * 90 + "\n\n")

    # Kontent i manifest
    idx = 0
    for p, sz in files:
        idx += 1
        entry = {
            "relpath": rel(p),
            "size": sz,
            "part": None,
            "type": "text" if (args.mode == "source" and is_text_ext(p)) else None,
            "sha256": None,
        }
        # Khesh
        try:
            entry["sha256"] = sha256_file(p)
        except Exception:
            entry["sha256"] = None

        # Predvaritelno pometim nomer chasti
        current_part = pw.part_idx if pw.part_idx > 0 else 1
        entry["part"] = current_part

        if args.mode == "source" and is_text_ext(p):
            dump_text_file(pw, p, sz)
        else:
            # Let's try as text; if it doesn’t work out, it’s like a binary
            try:
                with io.open(p, "r", encoding="utf-8") as f:
                    _ = f.read(4096)  # probnyy kusok
                dump_text_file(pw, p, sz)
                entry["type"] = "text"
            except Exception:
                dump_binary_file(pw, p, sz)
                entry["type"] = "binary-base64"

        # After recording, the file could go to a new part - check the actual part number
        entry["part"] = pw.part_idx
        manifest["entries"].append(entry)

    pw.close()
    manifest["parts"] = [
        {"index": i + 1, "name": PART_NAME.format(i + 1)} for i in range(len(pw.parts))
    ]

    manifest_path = Path(args.output_dir) / MANIFEST
    with io.open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, ensure_ascii=False, indent=2)

    # Extension: Log in store for Esther's memory
    state_dir = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
    vstore_dir = state_dir / "vstore"
    vstore_dir.mkdir(parents=True, exist_ok=True)
    dump_log = vstore_dir / "ester_dump_log.json"
    log_entry = {"ts": manifest["generated_at"], "files": manifest["files_total"], "bytes": manifest["bytes_total"]}
    if dump_log.exists():
        logs = json.loads(dump_log.read_text(encoding="utf-8"))
        logs.append(log_entry)
    else:
        logs = [log_entry]
    dump_log.write_text(json.dumps(logs, indent=2, ensure_ascii=False))

    dur = time.time() - start
    print(f"yuOKshch Ready: ZZF0Z parts, ZZF1ZZ files, ZZF2ZZ bytes")
    print(f"Manifest: {manifest_path}")
    print(f"Time: ZZF0ZZs")


if __name__ == "__main__":
    main()
# c=a+b