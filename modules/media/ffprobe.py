# -*- coding: utf-8 -*-
"""
modules/media/ffprobe.py — bystrye metadannye cherez ffprobe (s myagkim follbekom).

Mosty:
- Yavnyy: (Inzheneriya ↔ Multimedia) izvlekaem dlitelnost, dorozhki, kodeki.
- Skrytyy #1: (Infoteoriya ↔ Profile znaniya) schitaem sha256/razmer.
- Skrytyy #2: (Memory ↔ RAG) normalizuem polya dlya posleduyuschey zapis v pamyat.

Zemnoy abzats:
Kak «tekhnicheskiy profile» fayla: dlitelnost, razmer i chto vnutri — bez lishney magii.

# c=a+b
"""
from __future__ import annotations
import hashlib, json, os, subprocess
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

FFPROBE = os.getenv("FFPROBE_BIN","ffprobe")

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def probe(path: str) -> Dict[str,Any]:
    if not os.path.isfile(path):
        return {"ok": False, "error":"not_found"}
    size = os.path.getsize(path)
    sha = _sha256(path)
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
            capture_output=True, text=True, check=False
        )
        data = json.loads(r.stdout) if r.stdout.strip() else {}
        fmt = (data.get("format") or {})
        dur = float(fmt.get("duration", 0.0) or 0.0)
        streams = [{"codec_type": s.get("codec_type"), "codec_name": s.get("codec_name"),
                    "tags": s.get("tags",{}), "index": s.get("index")} for s in (data.get("streams") or [])]
        return {"ok": True, "path": path, "sha256": sha, "size": size, "duration": dur, "streams": streams, "raw": data}
    except Exception as e:
        # myagkiy follbek
        return {"ok": True, "path": path, "sha256": sha, "size": size, "duration": 0.0, "streams": [], "note": f"ffprobe_unavailable:{e}"}
# c=a+b