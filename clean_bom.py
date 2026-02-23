# -*- coding: utf-8 -*-
"""
clean_bom.py — Ochistka BOM (U+FEFF) iz faylov Ester.
Skaniruet .py/.txt/.json, udalyaet nevidimye simvoly, sokhranyaet original kak .bak.
Rasshirenie: Log v vstore, sha-proverka dlya pamyati Ester.

Zapusk: python clean_bom.py

# c=a+b
"""
from __future__ import annotations
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PROJECT_ROOT = Path(os.path.abspath(os.path.dirname(__file__)))
EXTS_TO_CLEAN = {".py", ".txt", ".json", ".md", ".yaml", ".yml"}

def compute_sha(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha.update(chunk)
    return sha.hexdigest()

def clean_file(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
        cleaned = content.replace("\ufeff", "")  # Udalyaem BOM
        if cleaned != content:
            bak_path = file_path.with_suffix(file_path.suffix + ".bak")
            file_path.rename(bak_path)  # Bekap originala
            file_path.write_text(cleaned, encoding="utf-8")
            return True
        return False
    except Exception as e:
        print(f"Oshibka v {file_path}: {e}")
        return False

def main():
    cleaned_files = []
    for root, _, files in os.walk(PROJECT_ROOT):
        for file in files:
            ext = Path(file).suffix.lower()
            if ext in EXTS_TO_CLEAN:
                path = Path(root) / file
                if clean_file(path):
                    sha = compute_sha(path)
                    cleaned_files.append({"relpath": str(path.relative_to(PROJECT_ROOT)), "sha": sha})

    # Log v vstore dlya pamyati Ester
    state_dir = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
    vstore_dir = state_dir / "vstore"
    vstore_dir.mkdir(parents=True, exist_ok=True)
    log_file = vstore_dir / "clean_bom_log.json"
    log_entry = {"ts": datetime.utcnow().isoformat(), "cleaned": len(cleaned_files), "files": cleaned_files}
    if log_file.exists():
        logs = json.loads(log_file.read_text(encoding="utf-8"))
        logs.append(log_entry)
    else:
        logs = [log_entry]
    log_file.write_text(json.dumps(logs, indent=2, ensure_ascii=False))

    print(f"[OK] Ochischeno {len(cleaned_files)} faylov. Log v {log_file}.")

if __name__ == "__main__":
    main()
# c=a+b