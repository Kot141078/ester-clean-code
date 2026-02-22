
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Patched line: optsionalnaya integratsiya s RAG cherez modules.media.rag_sink.maybe_ingest_text(meta)
"""
import os, json, time, shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = os.getenv("ESTER_MEDIA_AB","A").upper().strip() or "A"

AUDIO_EXT = {".wav",".mp3",".flac",".ogg",".m4a"}
VIDEO_EXT = {".mp4",".mkv",".mov",".avi",".webm"}
IMAGE_EXT = {".png",".jpg",".jpeg",".bmp",".gif",".webp"}
TEXT_EXT  = {".txt",".srt",".vtt",".md"}

ALL_EXT = AUDIO_EXT | VIDEO_EXT | IMAGE_EXT | TEXT_EXT

def _env_dir(key: str, default: str) -> Path:
    p = Path(os.getenv(key, default))
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_dirs() -> Dict[str, str]:
    in_dir  = _env_dir("ESTER_MEDIA_IN_DIR",  "data/media/in")
    out_dir = _env_dir("ESTER_MEDIA_OUT_DIR", "data/media/out")
    tmp_dir = _env_dir("ESTER_MEDIA_TMP_DIR", "data/media/tmp")
    return {"in": str(in_dir), "out": str(out_dir), "tmp": str(tmp_dir)}

def _classify(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in AUDIO_EXT: return "audio"
    if ext in VIDEO_EXT: return "video"
    if ext in IMAGE_EXT: return "image"
    if ext in TEXT_EXT:  return "text"
    return "other"

def _marker(out_dir: Path, src: Path) -> Path:
    return out_dir / f"{src.stem}.done.json"

def _is_processed(out_dir: Path, src: Path) -> bool:
    return _marker(out_dir, src).exists()

def _write_marker(out_dir: Path, src: Path, payload: Dict[str, Any]) -> None:
    m = _marker(out_dir, src)
    tmp = m.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, m)

def _video_probe(src: Path) -> Dict[str, Any]:
    try:
        from modules.video import ingest as vi  # type: ignore
        return vi.probe(str(src))
    except Exception as e:
        return {"ok": False, "reason": f"probe_error: {e}"}

def _voice_transcribe(src: Path) -> Dict[str, Any]:
    try:
        from modules import voice  # type: ignore
        return voice.transcribe(str(src))
    except Exception as e:
        return {"ok": False, "reason": f"transcribe_error: {e}"}

def _copy_out(src: Path, out_dir: Path) -> str:
    dest = out_dir / src.name
    try:
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)
    except Exception:
        pass
    return str(dest)

def process_file(src: Path, reason: str="scan") -> Dict[str, Any]:
    dirs = get_dirs()
    in_dir, out_dir = Path(dirs["in"]), Path(dirs["out"])
    meta: Dict[str, Any] = {"ts": int(time.time()), "src": str(src), "kind": _classify(src), "reason": reason, "ab": AB}
    try:
        if AB == "B":
            from modules.media import progress
            progress.record_event(str(src), "skipped_ab", meta)
            _write_marker(out_dir, src, {"ok": True, "skipped": True, **meta})
            return {"ok": True, "skipped": True, **meta}

        if meta["kind"] == "video":
            meta["probe"] = _video_probe(src)
        elif meta["kind"] == "audio":
            meta["transcribe"] = _voice_transcribe(src)
        elif meta["kind"] == "text":
            try:
                head = Path(src).read_text(encoding="utf-8", errors="ignore")[:1000]
            except Exception:
                head = ""
            meta["preview"] = head

        meta["out_copy"] = _copy_out(src, Path(dirs["out"]))
        _write_marker(out_dir, src, {"ok": True, **meta})

        from modules.media import progress
        progress.record_event(str(src), "processed", meta)

        # ---- NEW: optional RAG ingest ----
        if meta.get("kind") == "text":
            try:
                from modules.media import rag_sink
                rag_sink.maybe_ingest_text(meta)
            except Exception:
                pass

        return {"ok": True, **meta}
    except Exception as e:
        from modules.media import progress
        meta["error"] = str(e)
        progress.record_event(str(src), "failed", meta)
        try:
            _write_marker(out_dir, src, {"ok": False, **meta})
        except Exception:
            pass
        return {"ok": False, **meta}

def scan_once() -> List[str]:
    dirs = get_dirs()
    in_dir, out_dir = Path(dirs["in"]), Path(dirs["out"])
    files: List[str] = []
    for p in in_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in ALL_EXT:
            continue
        if _is_processed(out_dir, p):
            continue
        files.append(str(p))
    return sorted(files)

def tick(limit: int=10, reason: str="tick") -> Dict[str, Any]:
    pending = scan_once()[:max(0, limit)]
    done = []
    for s in pending:
        out = process_file(Path(s), reason=reason)
        done.append(out)
    from modules.media import progress
    summary = progress.summary()
    return {
        "ok": True,
        "queued": len(pending),
        "done": len(done),
        "events": summary.get("events_total", 0),
        "last": summary.get("last", []),
        "ab": AB,
    }
