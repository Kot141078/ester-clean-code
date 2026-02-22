# -*- coding: utf-8 -*-
"""
modules/audio/stt.py — oflayn/gibridnyy STT (whisper.cpp/Vosk/zaglushka) + SRT/VTT.

Mosty:
- Yavnyy: (Audio/Video ↔ Memory/RAG) transkript + subtitry pishem v fayly i v pamyat; pri nalichii rag_append — v RAG.
- Skrytyy #1: (Profile ↔ Prozrachnost) kazhdyy progon zhurnaliruem s kheshem i vremenem.
- Skrytyy #2: (Bind/Media ↔ Avtopotok) binder /bind/stt/run podtyagivaet novye media i vyzyvaet zdes transcribe().

Zemnoy abzats:
Eto «diktofon s bloknotom»: iz zvuka poluchaem tekst i subtitry, kladem ryadom s media i v pamyat, chtoby potom bystro iskat i tsitirovat.

# c=a+b
"""
from __future__ import annotations
import os, json, time, hashlib, subprocess, shlex, uuid, re
from typing import Dict, Any, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STT_DIR=os.getenv("STT_DIR","data/stt")
ENGINE=(os.getenv("STT_ENGINE","whisper_cpp") or "whisper_cpp").lower()
FFMPEG=os.getenv("STT_FFMPEG","ffmpeg")
LANG=os.getenv("STT_LANG","auto")

os.makedirs(STT_DIR, exist_ok=True)

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "audio://stt")
    except Exception:
        pass

def _hash(path: str)->str:
    try:
        st=os.stat(path)
        sig=f"{path}|{st.st_size}|{int(st.st_mtime)}"
    except Exception:
        sig=f"{path}|0|0"
    return hashlib.sha256(sig.encode("utf-8")).hexdigest()[:16]

def _wav16k(src: str)->str:
    out=os.path.join(STT_DIR, "tmp", f"{_hash(src)}.wav")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd=[FFMPEG,"-y","-i",src,"-ac","1","-ar","16000",out]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out

def _write(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",encoding="utf-8") as f: f.write(text)

def _simple_srt(text: str)->str:
    # Naivnaya razbivka po predlozheniyam, 3s na fragment
    parts=[p.strip() for p in re.split(r"[\\.!?\\n]+", text) if p.strip()]
    t=0.0; out=[]
    for i,p in enumerate(parts, start=1):
        t1=t; t2=t+3.0; t=t2
        def fmt(sec: float)->str:
            ms=int((sec-int(sec))*1000); s=int(sec)%60; m=(int(sec)//60)%60; h=int(sec)//3600
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        out.append(f"{i}\n{fmt(t1)} --> {fmt(t2)}\n{p}\n")
    return "\n".join(out) if out else "1\n00:00:00,000 --> 00:00:01,500\n...\n"

def _srt_to_vtt(srt: str)->str:
    return "WEBVTT\n\n"+srt.replace(",", ".")

def _rag_append(doc_id: str, text: str):
    try:
        from modules.media.utils import rag_append  # type: ignore
        rag_append(doc_id, text)
    except Exception:
        pass

def _engine_whisper(wav: str, lang: str, out_prefix: str)->Tuple[str,str]:
    bin_=os.getenv("WHISPER_BIN","./main")
    model=os.getenv("WHISPER_MODEL","models/ggml-base.bin")
    extra=os.getenv("WHISPER_EXTRA","")
    # -osrt -of <prefix> — sozdast <prefix>.srt i <prefix>.txt (pri nalichii -otxt, no mnogie sborki kladut txt v stdout — obrabotaem oba sluchaya)
    cmd=f"{shlex.quote(bin_)} -m {shlex.quote(model)} -f {shlex.quote(wav)} -l {shlex.quote(lang)} -osrt -of {shlex.quote(out_prefix)} {extra}"
    try:
        p=subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=360)
        txt_path=out_prefix+".txt"; srt_path=out_prefix+".srt"
        text=""
        if os.path.isfile(txt_path):
            text=open(txt_path,"r",encoding="utf-8",errors="ignore").read()
        else:
            text=p.stdout.decode("utf-8","ignore").strip()
        if not os.path.isfile(srt_path):
            # sdelaem prostye subtitry esli whisper ne vyvel
            _write(srt_path, _simple_srt(text))
        return text, open(srt_path,"r",encoding="utf-8").read()
    except Exception:
        return "", ""
        
def _engine_vosk(wav: str, lang: str)->Tuple[str,str]:
    model=os.getenv("VOSK_MODEL","")
    if not model:
        return "", ""
    try:
        import wave, json as _j
        from vosk import Model, KaldiRecognizer  # type: ignore
        wf=wave.open(wav, "rb")
        if wf.getnchannels()!=1 or wf.getsampwidth()!=2 or wf.getframerate()!=16000:
            return "", ""
        rec=KaldiRecognizer(Model(model), 16000)
        rec.SetWords(True)
        out=[]
        while True:
            data=wf.readframes(4000)
            if len(data)==0: break
            if rec.AcceptWaveform(data):
                j=_j.loads(rec.Result()); out.append(j.get("text",""))
        j=_j.loads(rec.FinalResult()); out.append(j.get("text",""))
        text=(" ".join(x for x in out if x)).strip()
        srt=_simple_srt(text)
        return text, srt
    except Exception:
        return "", ""

def transcribe(path: str, lang: str|None=None, out_dir: str|None=None)->Dict[str,Any]:
    if not os.path.isfile(path):
        return {"ok": False, "error":"path_not_found"}
    wav=_wav16k(path)
    out_dir=out_dir or os.path.join(STT_DIR, _hash(path))
    os.makedirs(out_dir, exist_ok=True)
    out_prefix=os.path.join(out_dir,"whisper")
    lang=lang or LANG
    text=""; srt=""
    if ENGINE=="whisper_cpp":
        text, srt=_engine_whisper(wav, lang, out_prefix)
    elif ENGINE=="vosk":
        text, srt=_engine_vosk(wav, lang)
    else:
        text=""; srt=""
    if not text:
        # zaglushka
        text="(no-speech or engine-missing)"
        srt=_simple_srt(text)
    vtt=_srt_to_vtt(srt)
    # zapisi
    txt_path=os.path.join(out_dir,"transcript.txt")
    srt_path=os.path.join(out_dir,"subtitles.srt")
    vtt_path=os.path.join(out_dir,"subtitles.vtt")
    _write(txt_path, text)
    _write(srt_path, srt)
    _write(vtt_path, vtt)
    # json metadannye
    rid=_hash(path)
    meta={
        "id": rid,
        "src": os.path.abspath(path),
        "engine": ENGINE,
        "lang": lang,
        "t": int(time.time()),
        "files": {"txt": txt_path, "srt": srt_path, "vtt": vtt_path}
    }
    _write(os.path.join(out_dir,"meta.json"), json.dumps(meta, ensure_ascii=False, indent=2))
    # profile + RAG
    _passport("stt_done", {"id": rid, "engine": ENGINE})
    try:
        _rag_append(f"stt-{rid}", text)
    except Exception:
        pass
    return {"ok": True, "id": rid, "meta": meta}
# c=a+b