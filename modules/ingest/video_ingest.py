# -*- coding: utf-8 -*-
"""modules/ingest/video_ingest.py - orkestrator: istochnik → metadannye → subtitry/ASR → chernovoy konspekt → sokhranenie v pamyat.

A/B-sloty (bezopasnaya samo-redaktura):
- VIDEO_INGEST_AB=A (by umolchaniyu): ASR cherez suschestvuyuschiy dvizhok asr_engine.asr_transcribe (drop-in).
- VIDEO_INGEST_AB=B: popytka ispolzovat faster-whisper (esli ustanovlen). Pri oshibke - avto-otkat na A.

Mosty:
- Yavnyy: (Memory ↔ Myshlenie) rezultaty kladutsya v StructuredMemory/VectorStore → dostupny thinking_pipeline i /chat (RAG-rezhim).
- Skrytyy #1: (Kibernetika ↔ Planirovschik) rezultaty atomarno registriruyutsya v ingest-dedup index, prigodny dlya paketnoy/f fonovoy obrabotki.
- Skrytyy #2: (Logika ↔ Interfeysy) drop-in API + sokhranenie faylov pod PERSIST_DIR, gotovo k buduschim /ingest/video-* ruchkam, bez lomki suschestvuyuschikh kontraktov.

Zemnoy abzats:
Eto “konveyer tsekha”: logist (video_sources) podaet zagotovku, stanki (ffmpeg/ASR) snimayut material, operator (summarizer)
delaet kratkiy report, kladovschik (memory) fiksiruet uchet. Vse vosproizvodimo i s zaschitoy ot dubley.

# c=a+b"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .video_common import (
    ProbeResult,
    audio_to_wav,
    chunk_wav,
    ensure_dir,
    ffprobe,
)
from .video_sources import SourceArtifacts, fetch_from_path, fetch_from_url
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Dedup and general index (ideomatic for existing ingest)
try:
    from modules.ingest.dedup_index import record_ingest, should_ingest, link_duplicate  # type: ignore
except Exception:
    def record_ingest(sha, path, size=0, meta=None): return {"sha": sha, "path": path, "size": size, "meta": meta or {}}
    def should_ingest(sha, size=0): return True
    def link_duplicate(sha, path): return {"sha": sha, "links": [path]}

# General utilities and memory
try:
    from modules.ingest.common import persist_dir, save_bytes, sha256_file as _sha256_file  # type: ignore
except Exception:
    from .video_common import sha256_file as _sha256_file  # type: ignore
    def persist_dir() -> str:
        root = os.path.abspath(os.path.join(os.getcwd(), "data"))
        os.makedirs(root, exist_ok=True)
        return root
    def save_bytes(path: str, data: bytes) -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

# NLP/Thinking: Soft Integration
def _maybe_summarize(text: str) -> str:
    """Tries to run thinking_pipelines.run_rules for summarization.
    Fullback - frequency keywords from modules.text_analyzer."""
    text = (text or "").strip()
    if not text:
        return ""
    # Trying via thinking_pipelines
    try:
        from modules.thinking_pipelines import run_rules  # type: ignore  # 
        rules = {"actions": [{"kind": "summarize", "hint": "video"}], "input": text[:20000]}
        rep = run_rules(rules)
        s = (rep or {}).get("summary") or (rep or {}).get("result") or ""
        if s:
            return str(s)
    except Exception:
        pass
    # Fulbeck: a simple “outline” through keywords
    try:
        from modules.text_analyzer import extract_keywords  # type: ignore  # 
        kws = extract_keywords(text, min_len=4)
        uniq = []
        seen = set()
        for w in kws:
            lw = w.lower()
            if lw not in seen:
                seen.add(lw)
                uniq.append(lw)
            if len(uniq) >= 50:
                break
        return "Key topics:" + ", ".join(uniq)
    except Exception:
        return text[:1000]

def _asr_file(path_wav: str) -> Tuple[str, List[Dict[str, Any]], str]:
    """Vozvraschaet (full_text, segments, backend).
    A/B: VIDEO_INGEST_AB=A|B"""
    ab = (os.getenv("VIDEO_INGEST_AB") or "A").strip().upper()
    # A - current engine asr_engine (drop-in)
    if ab == "A":
        try:
            from modules.ingest.asr_engine import asr_transcribe  # type: ignore
            rep = asr_transcribe(path_wav)
            segs = rep.get("segments") or []
            text = rep.get("text") or (" ".join(s.get("text","") for s in segs))
            return str(text or ""), list(segs), "A:asr_engine"
        except Exception as e:
            ab = "B"  # avto-otkat
    # B — faster-upper, if available
    try:
        from faster_whisper import WhisperModel  # type: ignore
        model_id = os.getenv("VIDEO_ASR_MODEL", "medium")
        device = "cuda" if os.getenv("USE_CUDA", "").strip() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        w = WhisperModel(model_id, device=device, compute_type=compute_type)
        segments, info = w.transcribe(path_wav, vad_filter=True, beam_size=5)
        text = []
        seg_list: List[Dict[str, Any]] = []
        for s in segments:
            seg_list.append({"start": float(s.start or 0.0), "end": float(s.end or 0.0), "text": s.text.strip()})
            text.append(s.text.strip())
        return " ".join(text).strip(), seg_list, "B:faster-whisper"
    except Exception as e:
        # final fullback - error out
        raise RuntimeError(f"ASR failed for both A and B: {e}")

def _merge_subs_or_asr(subs_paths: List[str], asr_text: str, asr_segments: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """If there is srt, we use it as the primary transcript (flat text + naive segments),
    otherwise we return the ACP result."""
    if subs_paths:
        buf: List[str] = []
        naive: List[Dict[str, Any]] = []
        for sp in subs_paths:
            try:
                with open(sp, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.isdigit():
                            continue
                        if "-->" in line:
                            # 00:00:01,000 --> 00:00:02,000 (propustim, segmenty naivno ne stroim tochno)
                            continue
                        buf.append(line)
            except Exception:
                continue
        text = " ".join(buf)
        if text.strip():
            return text[:2_000_000], naive
    return asr_text, asr_segments

def ingest_video(
    src: str,
    want_meta: bool = True,
    want_transcript: bool = True,
    want_summary: bool = True,
    prefer_audio: bool = True,
    want_subs: bool = True,
    chunk_ms: int = 5 * 60 * 1000,
) -> Dict[str, Any]:
    """Universalnaya tochka vkhoda: prinimaet URL or lokalnyy put.
    Vozvraschaet strukturu: {ok, source:{...}, probe:{...}, transcript:{text,segments}, summary, saved:{...}}"""
    # 1) Istochnik
    is_url = src.startswith("http://") or src.startswith("https://")
    art: SourceArtifacts = fetch_from_url(src, prefer_audio=prefer_audio, want_subs=want_subs) if is_url else fetch_from_path(src)

    # 2) Input artifact dedup
    try:
        sha = _sha256_file(art.local_path)
        if not should_ingest(sha, size=os.path.getsize(art.local_path)):
            link_duplicate(sha, art.local_path)
        else:
            record_ingest(sha, art.local_path, size=os.path.getsize(art.local_path), meta={"hints": ["video"]})
    except Exception:
        pass

    # 3) Metadannye
    probe: Optional[ProbeResult] = ffprobe(art.local_path) if want_meta else None

    # 4) Audio VAV (if not)
    wav_path = art.audio_path
    if wav_path and wav_path.lower().endswith(".m4a"):
        # m4a → wav
        out_dir = ensure_dir(os.path.join(art.workdir, "audio"))
        wav_path = os.path.join(out_dir, "audio.wav")
        wav_path = audio_to_wav(art.local_path, wav_path, sr=16000, mono=True)
    elif not wav_path:
        out_dir = ensure_dir(os.path.join(art.workdir, "audio"))
        wav_path = os.path.join(out_dir, "audio.wav")
        wav_path = audio_to_wav(art.local_path, wav_path, sr=16000, mono=True)

    # 5) Chankovanie i ASR
    transcript_text, transcript_segments, backend = "", [], ""
    if want_transcript:
        chunk_dir = ensure_dir(os.path.join(art.workdir, "audio_chunks"))
        chunks = chunk_wav(wav_path, chunk_dir, chunk_ms=chunk_ms, overlap_ms=5_000)
        # Simple serial build (compatible with existing scheduler, can be parallelized later)
        gathered: List[Dict[str, Any]] = []
        full: List[str] = []
        for (cp, start, end) in chunks:
            txt, segs, be = _asr_file(cp)
            backend = be
            if segs:
                # sdvigaem otnositelnye segmenty
                for s in segs:
                    s["start"] = float(s.get("start", 0.0)) + float(start)
                    s["end"] = float(s.get("end", 0.0)) + float(start)
                    gathered.append(s)
            if txt:
                full.append(txt)
        transcript_text = " ".join(full).strip()
        transcript_segments = gathered

    # 6) Subtitry vs ASR
    transcript_text, transcript_segments = _merge_subs_or_asr(art.subs_paths, transcript_text, transcript_segments)

    # 7) Kratkoe rezyume
    summary = _maybe_summarize(transcript_text) if (want_summary and transcript_text) else ""

    # 8) Saving to memory/storage (best-effort, soft imports)
    saved: Dict[str, Any] = {}
    try:
        from structured_memory import StructuredMemory  # type: ignore
        sm = StructuredMemory()
        rid = sm.add(text=(summary or transcript_text)[:2000], tags=["video", "summary" if summary else "transcript"])
        saved["structured_record_id"] = rid
    except Exception:
        pass
    # We will add it to the CG if there is an API commons (as in ingest text/pdf)
    try:
        from modules.ingest.common import kg_attach_artifact  # type: ignore
        label = Path(art.local_path).name
        kg_attach_artifact(label=label, text=(summary or transcript_text)[:4000], tags=["video"])
    except Exception:
        pass

    # 9) Finalnyy JSON
    out: Dict[str, Any] = {
        "ok": True,
        "source": {
            "workdir": art.workdir,
            "local_path": art.local_path,
            "meta_json": art.meta_json,
            "subs_paths": art.subs_paths,
        },
        "probe": probe.raw if (probe and probe.ok) else {"ok": False, "error": getattr(probe, "error", None)},
        "transcript": {"text": transcript_text, "segments": transcript_segments, "backend": backend},
        "summary": summary,
        "saved": saved,
        "ab": (os.getenv("VIDEO_INGEST_AB") or "A").strip().upper(),
    }
    # Place a copy of the result in PERSIST_HOLES for inspection
    try:
        import time as _t
        out_dir = ensure_dir(os.path.join(persist_dir(), "video_ingest"))
        fname = os.path.join(out_dir, f"rep_{int(_t.time())}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        out["dump_path"] = fname
    except Exception:
        pass
# return out