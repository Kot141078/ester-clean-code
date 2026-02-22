# -*- coding: utf-8 -*-
"""
modules/studio/video_compose.py — komponovka video (FFmpeg): shablony, bern-in SRT, vodyanoy znak.

Mosty:
- Yavnyy: (Studiya ↔ Video) sobiraet mp4 iz avatara/audiodramy/fonovogo tsveta/kartinok.
- Skrytyy #1: (Sotsdeploy ↔ Publikatsiya) kladet itog v STUDIO_OUT — SocialDeploy+ podkhvatit.
- Skrytyy #2: (Memory ↔ Profile) fiksiruet sborku (parametry/puti) dlya audita/RAG.

Zemnoy abzats:
Inzhenerno — «skleyschik»: berem gotovye dorozhki (golos/video), privodim k nuzhnomu formatu (9×16/16×9), pri neobkhodimosti prozhigaem subtitry i stavim vodyanoy znak. Na vykhode — rolik, gotovyy k zagruzke.

# c=a+b
"""
from __future__ import annotations
import os, re, glob, json, time, shutil, subprocess
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

FFMPEG=os.getenv("FFMPEG_BIN","ffmpeg")
OUT_DIR=os.getenv("STUDIO_OUT","data/studio/out")
TPL_DIR=os.getenv("VIDEO_TPL_DIR","data/studio/templates")
WATERMARK=os.getenv("VIDEO_WATERMARK","").strip()
DEF_FONT=os.getenv("VIDEO_DEFAULT_FONT","Arial")

def _ensure():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TPL_DIR, exist_ok=True)
    # bazovye shablony, esli pusto
    base=os.path.join(TPL_DIR, "short_vertical_avatar.json")
    if not os.path.isfile(base):
        json.dump({
          "name":"short_vertical_avatar",
          "aspect":"9x16",
          "use":"last_avatar_or_color",
          "background":"color:black",
          "bgm":"auto",   # vozmem poslednyuyu muzyku iz studii, esli naydem
          "burn_subs":"auto",
          "watermark":"env"
        }, open(base,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _mm_passport(note: str, meta: Dict[str,Any])->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="studio://video")
    except Exception:
        pass

def _have_ffmpeg()->bool:
    return shutil.which(FFMPEG) is not None

def _find_last(patterns: List[str])->str|None:
    files=[]
    for p in patterns:
        files.extend(glob.glob(p))
    files=sorted(files)
    return files[-1] if files else None

def _aspect_to_size(aspect: str)->Tuple[int,int]:
    a=(aspect or "9x16").lower()
    if a=="16x9":  return (1920,1080)
    if a=="1x1":   return (1080,1080)
    return (1080,1920)  # 9x16

def _make_color_video(size: Tuple[int,int], duration_sec: int, dst: str)->bool:
    if not _have_ffmpeg(): return False
    w,h=size
    try:
        p=subprocess.run([FFMPEG,"-y","-f","lavfi","-i",f"color=c=black:s={w}x{h}:d={int(max(1,duration_sec))}", "-c:v","libx264","-pix_fmt","yuv420p", dst],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        return p.returncode==0 and os.path.isfile(dst)
    except Exception:
        return False

def _probe_duration(path: str)->float:
    # grubaya otsenka dlitelnosti v sekundakh (cherez ffprobe, esli dostupno)
    ffprobe = "ffprobe"
    if not shutil.which(ffprobe): return 0.0
    try:
        p=subprocess.run([ffprobe,"-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", path],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        s=p.stdout.decode("utf-8").strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0

def _apply_subs_filter(filters: List[str], subs: str)->None:
    # Prozhig SRT/ASS, esli filtr dostupen
    if subs and os.path.isfile(subs):
        # subs filtr sam opredelit format
        filters.append(f"subtitles='{subs}'")

def _apply_watermark(inputs: List[str], maps: List[str], filters: List[str])->None:
    wm=WATERMARK
    if wm and os.path.isfile(wm):
        inputs.extend(["-i", wm])
        # Pomestim v pravyy verkhniy ugol s otstupom
        filters.append("[0:v][1:v]overlay=W-w-24:24")

def _compose_cmd(video_src: str, audio_src: str|None, size: Tuple[int,int], subs: str|None, dst: str)->List[str]:
    # Sobiraem ffmpeg komandu s masshtabom i paddingom do nuzhnogo sootnosheniya
    w,h=size
    vf=[]
    # Privedenie k trebuemomu aspektu
    vf.append(f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease")
    vf.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black")
    if subs: _apply_subs_filter(vf, subs)
    # Vodyanoy znak
    inputs=["-i", video_src]
    maps=[]
    _apply_watermark(inputs, maps, vf)
    cmd=[FFMPEG,"-y"] + inputs
    if audio_src and os.path.isfile(audio_src):
        cmd+=["-i", audio_src]
        amix = ["-filter_complex", ";".join(vf) if vf else "null", "-map","0:v","-map","1:a","-c:v","libx264","-c:a","aac","-shortest"]
        cmd+=amix
    else:
        if vf: cmd+=["-vf",";".join(vf)]
        cmd+=["-c:v","libx264"]
    cmd+=["-pix_fmt","yuv420p", dst]
    return cmd

def _auto_pick_subs()->str|None:
    # vzyat posledniy SRT iz studii (drama/kit)
    return _find_last(["data/studio/drama/*/drama.srt","data/studio/out/*.srt"])

def _auto_pick_bgm()->str|None:
    return _find_last(["data/studio/out/music_*.wav","data/studio/out/music_last.wav","data/studio/out/*.mp3","data/studio/drama/*/drama.mp3"])

def _auto_pick_avatar()->str|None:
    return _find_last(["data/studio/avatar_cache/*_host.mp4","data/studio/out/*avatar*.mp4","data/studio/out/*.mp4"])

def list_templates()->List[Dict[str,Any]]:
    _ensure()
    out=[]
    for f in sorted(glob.glob(os.path.join(TPL_DIR,"*.json"))):
        try:
            j=json.load(open(f,"r",encoding="utf-8"))
            out.append({"name": j.get("name") or os.path.basename(f).replace(".json",""), "path": f})
        except Exception:
            pass
    return out

def compose(title: str, aspect: str, template: str|None, subs: str|None, audio: str|None, video: str|None, background: str|None, duration_sec: int|None)->Dict[str,Any]:
    """
    Libo daem template, libo yavnye puti (video/audio/subs). background mozhet byt "color:black".
    """
    _ensure()
    size=_aspect_to_size(aspect or "9x16")
    ts=int(time.time())
    out=os.path.join(OUT_DIR, f"{(title or 'Video').replace(' ','_')}_{aspect or '9x16'}_{ts}.mp4")

    # Raskryt shablon
    if template:
        path=os.path.join(TPL_DIR, f"{template}.json")
        if os.path.isfile(path):
            t=json.load(open(path,"r",encoding="utf-8"))
        else:
            t={"use":"last_avatar_or_color","aspect": aspect or "9x16", "burn_subs":"auto","background":"color:black"}
        # avatar or color
        if (t.get("use")=="last_avatar_or_color") and not video:
            video=_auto_pick_avatar()
            if not video and (background or t.get("background","")).startswith("color:"):
                # sdelaem tsvetnoy fon na nuzhnuyu dlitelnost (po audio, esli est)
                d=int(duration_sec or 0)
                if not d and audio and os.path.isfile(audio): d=int(_probe_duration(audio)) or 10
                tmp=os.path.join(OUT_DIR, f"bg_{ts}.mp4")
                if _make_color_video(size, d or 10, tmp):
                    video=tmp
        if (t.get("burn_subs")=="auto") and not subs:
            subs=_auto_pick_subs()
        if (t.get("bgm")=="auto") and not audio:
            audio=_auto_pick_bgm()
        if (t.get("watermark")=="env") and not WATERMARK:
            # optsionalno ostavim pustym
            pass

    # Esli prosyat fon "color:" yavno
    if (background or "").startswith("color:") and not video:
        color=background.split(":",1)[1] if ":" in (background or "") else "black"
        # tsvet berem cherez lavfi color, no my oborachivaem vyshe — zdes prosto sdelaem v _make_color_video
        d=int(duration_sec or 0)
        if not d and audio and os.path.isfile(audio): d=int(_probe_duration(audio)) or 10
        tmp=os.path.join(OUT_DIR, f"bg_{ts}.mp4")
        if _make_color_video(size, d or 10, tmp):
            video=tmp

    # sanity
    if not video:
        # krayniy sluchay — 10s chernogo
        tmp=os.path.join(OUT_DIR, f"bg_{ts}.mp4")
        _make_color_video(size, int(duration_sec or 10), tmp)
        video=tmp

    if not _have_ffmpeg():
        rep={"ok": False, "error":"ffmpeg_not_found"}
        _mm_passport("video_compose", rep)
        return rep

    cmd=_compose_cmd(video, audio, size, subs, out)
    try:
        p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=216000)
        ok=(p.returncode==0 and os.path.isfile(out))
    except Exception as e:
        ok=False

    meta={"title": title, "aspect": aspect, "template": template, "subs": subs, "audio": audio, "video": video, "out": out, "ok": bool(ok)}
    _mm_passport("video_compose", meta)
    return {"ok": bool(ok), "out": out, "meta": meta}
# c=a+b



