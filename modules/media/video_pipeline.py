# -*- coding: utf-8 -*-
"""modules/media/video_pipeline.py - PROBE i INGEST video: metadannye, subtitry, transkript, konspekt.

Mosty:
- Yavnyy: (Video ↔ Memory) obekt v reestre, subtitry/transkript v pamyat, konspekt v RAG i KG.
- Skrytyy #1: (LegalGuard/IngestGuard ↔ Ostorozhnost) svetofor i kvoty pered setevymi shagami.
- Skrytyy #2: (Profile ↔ Audit) vse etapy shtampuyutsya.

Zemnoy abzats:
Avtomaticheskaya "vytyazhka" iz video: vzyat razreshennoe, berezhno obrabotat i ulozhit na polki - chtoby potom bystro vspomnit.

# c=a+b"""
from __future__ import annotations
import os, json, time, re
from typing import Any, Dict, List, Tuple

from modules.media.utils import (
    ensure_db, load_db, save_db, vid_id, shell,
    legal_check, ingest_quota, passport, mem_append, kg_autolink, rag_append,
    MEDIA_DIR
)
from modules.media.summarize import draft_notes
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

YTDLP = os.getenv("YTDLP_BIN","yt-dlp")
FFMPEG = os.getenv("FFMPEG_BIN","ffmpeg")
WHISPER = os.getenv("WHISPER_BIN","")
MAX_MIN = int(os.getenv("MEDIA_MAX_DURATION_MIN","240") or "240")
T_MAX_MIN = int(os.getenv("MEDIA_TRANSCRIBE_MAX_MIN","60") or "60")

def _safe_name(s: str)->str:
    return re.sub(r"[^A-Za-z0-9_\-\.]+","_", s)[:80]

def _probe_local(path: str)->Dict[str,Any]:
    if not path or not os.path.isfile(path): 
        return {"ok": False, "error":"file_not_found"}
    meta={"path": os.path.abspath(path)}
    # ffprobe simplified: only duration
    if FFMPEG:
        code,out,err=shell(f'{FFMPEG} -i "{path}" -hide_banner')
        dur=None
        for line in (err or out).splitlines():
            m=re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", line)
            if m:
                h,mn,sc=m.groups()
                dur=int(h)*60+int(mn)+ (1 if float(sc)>0 else 0)
                break
        if dur: meta["duration_min"]=dur
    return {"ok": True, "meta": meta, "subs_available": False}

def _probe_ytdlp(url: str)->Dict[str,Any]:
    # bez skachivaniya: --skip-download --print-json
    code,out,err=shell(f'{YTDLP} -J --skip-download "{url}"', timeout=90)
    if code!=0:
        return {"ok": False, "error":"ytdlp_failed", "stderr": err}
    try:
        j=json.loads(out)
    except Exception:
        return {"ok": False, "error":"ytdlp_json_error"}
    dur=int(j.get("duration") or 0)
    subs= bool((j.get("subtitles") or {}) or (j.get("automatic_captions") or {}))
    meta={
        "title": j.get("title"),
        "uploader": j.get("uploader"),
        "webpage_url": j.get("webpage_url") or url,
        "duration_min": int(round(dur/60.0))
    }
    return {"ok": True, "meta": meta, "subs_available": subs}

def probe(url: str|None=None, path: str|None=None)->Dict[str,Any]:
    ensure_db()
    if url:
        # LegalGuard
        lg=legal_check("web_scrape", "public_video")
        if lg.get("verdict")=="deny":
            return {"ok": False, "error":"legal_denied", "reasons": lg.get("reasons",[])}
        return _probe_ytdlp(url)
    elif path:
        return _probe_local(path)
    return {"ok": False, "error":"no_input"}

def _download_ytdlp(url: str, outdir: str)->Tuple[Dict[str,Any], str|None, str|None]:
    os.makedirs(outdir, exist_ok=True)
    # download the best audio and subtitles (if available)
    cmd = f'{YTDLP} -o "{os.path.join(outdir,"%(_id)s.%(ext)s")}" --write-auto-sub --write-sub --sub-lang "en.*,ru.*" --skip-download --print-json "{url}"'
    code,out,err = shell(cmd, timeout=180)
    if code!=0:
        return ({"ok": False, "error":"ytdlp_meta_failed","stderr": err}, None, None)
    try:
        j=json.loads(out.splitlines()[-1])
    except Exception:
        j={}
    # subtitles could be pumped out nearby
    sub_file=None
    for root,_,files in os.walk(outdir):
        for n in files:
            if n.endswith(".vtt") or n.endswith(".srt"):
                sub_file=os.path.join(root,n); break
    # you can also download audio (optional)
    audio_file=None
    acode,aout,aerr = shell(f'{YTDLP} -x --audio-format mp3 -o "{os.path.join(outdir,"%(_id)s.%(ext)s")}" "{url}"', timeout=21600)
    if acode==0:
        for n in os.listdir(outdir):
            if n.endswith(".mp3"): audio_file=os.path.join(outdir,n); break
    return ({"ok": True, "meta": j}, sub_file, audio_file)

def _transcribe(audio_path: str, outdir: str)->Tuple[bool,str|None]:
    if not WHISPER: 
        return (False, None)
    os.makedirs(outdir, exist_ok=True)
    out=os.path.join(outdir, "transcript.txt")
    code,_,_ = shell(f'{WHISPER} "{audio_path}" --output-txt --output_dir "{outdir}"', timeout=21600)
    if code==0 and os.path.isfile(out):
        return (True, out)
    return (False, None)

def _read_textsafe(path: str)->str:
    try:
        return open(path,"r",encoding="utf-8").read()
    except Exception:
        return ""

def _store_index(entry: Dict[str,Any])->None:
    j=load_db(); arr=j.get("items",[])
    # upsert po id
    found=False
    for i,x in enumerate(arr):
        if x.get("id")==entry["id"]:
            arr[i]=entry; found=True; break
    if not found: arr.append(entry)
    j["items"]=arr; save_db(j)

def ingest(url: str|None=None, path: str|None=None, prefer_subs: bool=True, transcribe: bool=False)->Dict[str,Any]:
    ensure_db()
    src = url or path or ""
    if not src: return {"ok": False, "error":"no_input"}

    # LegalGuard
    kind = "web_scrape" if url else "subtitle_extract"
    lg=legal_check(kind, "public_video" if url else "local_video")
    if lg.get("verdict")=="deny":
        return {"ok": False, "error":"legal_denied", "reasons": lg.get("reasons",[])}

    vid=vid_id(src)
    vdir=os.path.join(MEDIA_DIR, vid); os.makedirs(vdir, exist_ok=True)
    meta={"id": vid, "source": ("url" if url else "path"), "src": src, "ts": int(time.time())}
    passport("media_ingest_start", {"id": vid, "src": src[:120]}, "media://ingest")

    subs_text=""; transcript_text=""; notes=None

    if url:
        # quota: let's estimate the base "cost" as 10 tokens + 1/minute (approximately)
        pr=probe(url=url); minutes=int(pr.get("meta",{}).get("duration_min") or 0)
        qt=ingest_quota("youtube", 10 + max(0, minutes))
        if not qt.get("allowed"):
            return {"ok": False, "error":"rate_limited", "retry_after_sec": qt.get("retry_after_sec",30)}
        rep, sub_file, audio_file = _download_ytdlp(url, vdir)
        meta["ytdlp"]=rep
        if sub_file and prefer_subs:
            subs_text=_read_textsafe(sub_file)
        if transcribe and audio_file and minutes<=T_MAX_MIN:
            ok, tpath=_transcribe(audio_file, vdir)
            if ok and tpath: transcript_text=_read_textsafe(tpath)
    else:
        # lokalnyy fayl: poprobuem vydrat vstroennye subtitry i audio
        if prefer_subs and FFMPEG:
            # ffmpeg cannot always pull subtitles out of the container - best-effort
            pass
        if transcribe and FFMPEG and os.path.isfile(path or "") and T_MAX_MIN>0:
            # pull out the audio (mp3) and play it downward, if there is one
            apath=os.path.join(vdir,"audio.mp3")
            code,_,_=shell(f'{FFMPEG} -i "{path}" -vn -acodec libmp3lame -y "{apath}"', timeout=21600)
            if code==0 and os.path.isfile(apath):
                ok, tpath=_transcribe(apath, vdir)
                if ok and tpath: transcript_text=_read_textsafe(tpath)

    full_text = (subs_text.strip() or transcript_text.strip() or "")
    if full_text:
        notes = draft_notes(full_text, limit=12)
        # v pamyat — kuskami po 2-3k simvolov
        CHUNK=1800
        for i in range(0, len(full_text), CHUNK):
            chunk=full_text[i:i+CHUNK]
            mem_append(chunk, {"kind":"media_text","video_id": vid, "i": i//CHUNK})
        # autolink of entities across several chunks (the first 2 and a summary)
        items=[]
        if len(full_text)>0:
            items.append({"id": f"{vid}-t0", "text": full_text[:3000]})
        if notes and notes.get("ok"):
            items.append({"id": f"{vid}-notes", "text": " ".join(notes.get("bullets",[]))})
        if items: kg_autolink(items)
        # RAG fallback — dobavlyaem zametki+kusok
        rag_append(f"{vid}-notes", " ".join((notes or {}).get("bullets",[])))
        rag_append(f"{vid}-t0", full_text[:3000])

    entry={
        "id": vid,
        "kind": "video",
        "meta": meta,
        "paths": {"dir": vdir},
        "has_subs": bool(subs_text),
        "has_transcript": bool(transcribe and transcript_text),
        "notes": notes or {"ok": True, "bullets": []}
    }
    _store_index(entry)
    passport("media_ingest_done", {"id": vid, "subs": bool(subs_text), "tr": bool(transcript_text)}, "media://ingest")
    return {"ok": True, "id": vid, "entry": entry}

def status(vid: str)->Dict[str,Any]:
    j=load_db()
    for it in j.get("items",[]):
        if it.get("id")==vid:
            return {"ok": True, "entry": it}
    return {"ok": False, "error":"not_found"}

def list_items(limit: int=50)->Dict[str,Any]:
    j=load_db()
    arr=list(reversed(j.get("items",[])))[:max(1,int(limit))]
    return {"ok": True, "items": arr}
# c=a+b


