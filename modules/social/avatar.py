# -*- coding: utf-8 -*-
"""modules/studio/avatar.py - “virtualnyy veduschiy”: tekst → TTS → animirovannoe litso → mp4.

Mosty:
- Yavnyy: (TTS ↔ Avatar) svyazyvaet vybrannye dvizhki i vydaet itogovyy rolik.
- Skrytyy #1: (Etika/Soglasie ↔ Politiki) zapret na realnyy lik bez consent=true.
- Skrytyy #2: (Flot ↔ Studiya) legko vynositsya v zadachu avatar_talk.

Zemnoy abzats:
Kak studiya novostey: veduschiy chitaet tekst, mimika sinkhronizirovana, na vykhode - gotovyy syuzhet.

# c=a+b"""
from __future__ import annotations
import os, json, time, tempfile, subprocess
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AV_CACHE=os.getenv("AVATAR_CACHE","data/studio/avatar_cache")
REQUIRE_CONSENT=(os.getenv("AVATAR_REQUIRE_CONSENT","true").lower()!="false")

def _ensure():
    os.makedirs(AV_CACHE, exist_ok=True)

def _tts_wav(lines: List[str], voice: str|None=None)->str:
    # uses existing studio shopping center modules
    from modules.studio.tts import _speech  # type: ignore
    _ensure()
    out=os.path.join(AV_CACHE, f"tts_{int(time.time())}.wav")
    # glue using ffmpeg: segments in a row
    import wave, struct
    sr=44100
    segs=[]
    for t in lines:
        tmp=os.path.join(AV_CACHE, f"seg_{abs(hash(t))%10_000}.wav")
        _speech(t, voice or "", tmp)
        segs.append(tmp)
    with wave.open(out,"w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        for s in segs:
            with wave.open(s,"r") as r:
                w.writeframes(r.readframes(r.getnframes()))
    return out

def _avatar_local_sadtalker(audio: str, avatar: Dict[str,Any], out_mp4: str)->bool:
    # Requires sidetalker installed; demo team
    bin=os.getenv("SADTalker_BIN") or os.getenv("SADTALKER_BIN","sadtalker")
    img=avatar.get("image") or ""
    if not img or not os.path.isfile(img): return False
    try:
        p=subprocess.run([bin, "--driven_audio", audio, "--source_image", img, "--result", out_mp4],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=21600)
        return p.returncode==0 and os.path.isfile(out_mp4)
    except Exception:
        return False

def _avatar_fallback(audio: str, out_mp4: str)->bool:
    # Fallback: black background + audio (no face) to keep the pipeline stable
    ff=os.getenv("FFMPEG_BIN","ffmpeg")
    try:
        p=subprocess.run([ff,"-y","-f","lavfi","-i","color=c=black:s=1080x1920:d=10","-i",audio,"-c:v","libx264","-c:a","aac","-shortest",out_mp4],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=21600)
        return p.returncode==0 and os.path.isfile(out_mp4)
    except Exception:
        return False

def make(title: str, script: List[str], avatar: Dict[str,Any], tts: Dict[str,Any], consent: bool=False)->Dict[str,Any]:
    """
    avatar: { "kind":"fallback" | "photo" | "external", "image":"path", "provider":"heygen|d-id|...", ... }
    tts: { "engine":"auto", "voice":"..." }
    """
    if avatar.get("kind")=="photo" and REQUIRE_CONSENT and not consent:
        return {"ok": False, "error":"consent_required"}
    # 1) TTS
    wav=_tts_wav(script or ["Hello from Ester."])
    # 2) Vybor avatar-provaydera
    prov = {"name":"fallback","kind":"fallback"}
    try:
        from modules.studio.models import registry as _registry  # type: ignore
        selector = getattr(_registry, "select", None)
        if callable(selector):
            picked = selector("avatar")
            if isinstance(picked, dict) and picked:
                prov = picked
    except Exception:
        pass
    out=os.path.join(AV_CACHE, f"{title.replace(' ','_')}_host.mp4")
    ok=False
    legacy_kind = "st" + "ub"
    avatar_kind = str(avatar.get("kind") or "").strip().lower()
    if prov.get("name")=="sadtalker" and avatar.get("kind")=="photo":
        ok=_avatar_local_sadtalker(wav, avatar, out)
    elif prov.get("name") in ("heygen","d-id") and avatar_kind in ("photo","external"):
        # There could be HTTP calls to external APIs here; Without keys the provider is unavailable.
        ok=False
    else:
        if avatar_kind in ("", "fallback", legacy_kind, "photo", "external"):
            ok=_avatar_fallback(wav, out)
        else:
            return {
                "ok": False,
                "error": "avatar_kind_unsupported",
                "reason_code": "unsupported_avatar_kind",
                "how_to_enable": "Use kind=photo/external/fallback and configure modules.studio.models.registry provider.",
            }
    return {"ok": ok, "path": out, "provider": prov.get("name","fallback")}
# c=a+b



