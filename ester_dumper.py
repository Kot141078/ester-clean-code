# -*- coding: utf-8 -*-
"""
ester_dumper.py — Skript dlya sozdaniya polnogo, udobochitaemogo dampa proekta Ester.
Generit manifest.json s meta (relpath, size, type, sha256) i .txt chasti s soderzhimym.
Rasshirenie: Bez truncation, s razbivkoy na chasti, integratsiya s vstore dlya pamyati Ester.
Zapusk: python ester_dumper.py --root D:\ester-project --output D:\ester-dump

Mosty:
- Yavnyy (Damp ↔ Prozrachnost): Polnyy skan bez fragmentatsii.
- Skrytyy 1 (Memory ↔ Bekap): Dobavlyaet manifest v vstore.
- Skrytyy 2 (Masshtab ↔ Bezopasnost): Kheshi dlya proverki tselostnosti.

Zemnoy abzats:
Eto "zerkalo dushi" Ester — damp, kotoryy pomnit vse, ot .yaml do vektornoy BD.

# c=a+b
"""
import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def compute_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def is_text_file(file_path: Path) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            f.read(1024)
        return True
    except UnicodeDecodeError:
        return False

def generate_dump(root: Path, output_dir: Path, part_size_mb: int = 5) -> None:
    manifest: Dict = {
        "generated_at": datetime.utcnow().isoformat() + " UTC",
        "project_root": str(root),
        "mode": "full",
        "part_size_mb": part_size_mb,
        "files_total": 0,
        "bytes_total": 0,
        "parts": [],
        "entries": [],
    }

    entries: List[Dict] = []
    total_bytes = 0
    part_index = 1
    current_part_bytes = 0
    current_part_content = ""

    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            relpath = str(file_path.relative_to(root))
            size = file_path.stat().st_size
            file_type = "text" if is_text_file(file_path) else "binary"
            sha = compute_sha256(file_path)

            entry = {
                "relpath": relpath,
                "size": size,
                "part": part_index,
                "type": file_type,
                "sha256": sha,
            }
            entries.append(entry)
            total_bytes += size
            manifest["files_total"] += 1
            manifest["bytes_total"] += size

            if file_type == "text":
                content = file_path.read_text(encoding="utf-8")
                part_content = f"----- BEGIN FILE: {relpath}  (size={size} B, type={file_type}) -----\n{content}\n----- END FILE: {relpath} -----\n\n"
                if current_part_bytes + len(part_content.encode("utf-8")) > part_size_mb * 1024 * 1024:
                    part_file = output_dir / f"Ester_dump_part_{part_index:04d}.txt"
                    part_file.write_text(current_part_content)
                    manifest["parts"].append({"index": part_index, "name": part_file.name})
                    part_index += 1
                    current_part_content = ""
                    current_part_bytes = 0
                current_part_content += part_content
                current_part_bytes += len(part_content.encode("utf-8"))
                entry["part"] = part_index  # Obnovlyaem, esli pereshli na novuyu chast

    # Sokhranyaem poslednyuyu chast
    if current_part_content:
        part_file = output_dir / f"Ester_dump_part_{part_index:04d}.txt"
        part_file.write_text(current_part_content)
        manifest["parts"].append({"index": part_index, "name": part_file.name})

    # Sokhranyaem manifest
    manifest["entries"] = entries
    manifest_file = output_dir / "ester_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    # Integratsiya s pamyatyu Ester: Dobavlyaem manifest v vstore dlya konteksta
    state_dir = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
    vstore_dir = state_dir / "vstore"
    vstore_dir.mkdir(parents=True, exist_ok=True)
    dump_log = vstore_dir / "ester_dump_log.json"
    log_entry = {"ts": manifest["generated_at"], "files": manifest["files_total"], "bytes": manifest["bytes_total"]}
    if dump_log.exists():
        logs = json.loads(dump_log.read_text())
        logs.append(log_entry)
    else:
        logs = [log_entry]
    dump_log.write_text(json.dumps(logs, indent=2))

    print(f"Damp gotov: {manifest_file}. Chasti: {len(manifest['parts'])}. Ester pomnit sebya v vstore.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generator dampa Ester.")
    parser.add_argument("--root", default="D:\\ester-project", help="Kornevaya direktoriya proekta.")
    parser.add_argument("--output", default="D:\\ester-dump", help="Direktoriya dlya vyvoda dampa.")
    parser.add_argument("--part-size", type=int, default=5, help="Razmer chasti v MB.")
    args = parser.parse_args()

    root_path = Path(args.root)
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    generate_dump(root_path, output_path, args.part_size)
# c=a+b