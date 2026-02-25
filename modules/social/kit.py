# -*- coding: utf-8 -*-
"""modules/social/kit.py - formirovanie upload-kit dlya platform (TikTok/YouTube/Patreon/Instagram).

Mosty:
- Yavnyy: (Kontent ↔ Publikatsiya) sobiraem papku s video/audio/thumbnail + metadata.json + chek-list + instruktsii.
- Skrytyy #1: (Studiya ↔ Sotsset) perevarivaem assety iz ContentStudio (mp4/wav/ass/srt).
- Skrytyy #2: (Memory ↔ Profile) fiksiruem vypusk kita v pamyat dlya audita i RAG.
- Skrytyy #3: (Ekonomika ↔ Monetizatsiya) gotovye kity s kheshami uproschayut prodazhi/posting.

Zemnoy abzats:
How “sumka montazhera pered ploschadkoy”: vse slozheno i podpisano - video, subtitry, oblozhka, JSON metadannykh, kheshi dlya verifikatsii i gotovye podskazki, kuda zhat na sayte. Teper s list_kits dlya obzora - beri i zagruzhay, dazhe esli API nedostupny.

# c=a+b"""
from __future__ import annotations
import os, json, time, glob, shutil, hashlib
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.getenv("SOCIAL_ROOT", "data/social")
OUT = os.getenv("SOCIAL_OUT", "data/social/kits")

def _ensure():
    os.makedirs(ROOT, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)

def _mm_passport(note: str, meta: Dict[str, Any]) -> None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm = get_mm()
        upsert_with_passport(mm, note, meta, source="social://kit")
    except Exception:
        pass

def _find_last(patterns: List[str]) -> str | None:
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    files = sorted(files, key=os.path.getmtime)
    return files[-1] if files else None

def _auto_media() -> Dict[str, str]:
    return {
        "video": _find_last(["data/studio/out/*_9x16.mp4", "data/studio/out/*.mp4", "data/studio/avatar_cache/*_host.mp4"]),
        "audio": _find_last(["data/studio/out/*drama.wav", "data/studio/out/music_*.wav", "data/studio/out/music_last.wav"]),
        "subs": _find_last(["data/studio/tmp/subs.ass", "data/studio/out/*.ass", "data/studio/drama/*/drama.srt", "data/studio/out/*.srt"]),
        "thumb": _find_last(["data/studio/out/*.png", "data/studio/out/*.jpg"])
    }

def _srt_from_ass(ass_path: str, srt_path: str) -> bool:
    try:
        from modules.social.subs import ass_to_srt  # type: ignore
        txt = open(ass_path, "r", encoding="utf-8").read()
        srt = ass_to_srt(txt)
        open(srt_path, "w", encoding="utf-8").write(srt)
        return True
    except Exception:
        return False

def _mk_thumbnail(title: str, dst_dir: str) -> str:
    try:
        from modules.social.thumb import make_thumbnail  # type: ignore
        th = make_thumbnail(title, dst_dir)
        return th
    except Exception:
        # Alternate route: simple SVG
        svg = os.path.join(dst_dir, "thumb.svg")
        tt = title.replace("&", "&amp;").replace("<", "&lt;")
        open(svg, "w", encoding="utf-8").write(
            f"<svg xmlns='http://www.w3.org/2000/svg' width='1280' height='720'><rect width='100%' height='100%' fill='#111'/><text x='50' y='360' fill='#fff' font-size='64' font-family='Arial'>{tt}</text></svg>"
        )
        return svg

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def build(platform: str, title: str, description: str, tags: List[str], assets: Dict[str, Any] | None = None, schedule_ts: int | None = None) -> Dict[str, Any]:
    """
    platform: tiktok|youtube_short|youtube_long|patreon_post|instagram_reels
    assets: { "video": "path or auto", "audio": "...", "subs": "...", "thumb": "..." }
    """
    _ensure()
    ts = int(time.time())
    slug = f"{platform}_{ts}"
    kit_dir = os.path.join(OUT, slug)
    os.makedirs(kit_dir, exist_ok=True)

    auto = _auto_media()
    assets = dict(assets or {})
    for key in ["video", "audio", "subs", "thumb"]:
        if assets.get(key) == "auto" or not assets.get(key):
            assets[key] = auto.get(key)

    # Kopiruem assety
    copied = {}
    for key, src in assets.items():
        if src and os.path.isfile(src):
            dst = os.path.join(kit_dir, os.path.basename(src))
            shutil.copy2(src, dst)
            copied[key] = dst

    # Konvertirovat v .srt pri neobkhodimosti
    if copied.get("subs", "").lower().endswith(".ass"):
        srt_path = os.path.join(kit_dir, "subtitles.srt")
        if _srt_from_ass(copied["subs"], srt_path):
            copied["subs"] = srt_path

    # Preview if not provided
    if not copied.get("thumb"):
        thumb = _mk_thumbnail(title, kit_dir)
        copied["thumb"] = thumb

    # Metadata
    meta = {
        "platform": platform,
        "title": title[:100],
        "description": description[:5000],
        "tags": tags[:25],
        "schedule_ts": schedule_ts,
        "files": {k: os.path.basename(v) if v else "" for k, v in copied.items()}
    }
    meta_path = os.path.join(kit_dir, "metadata.json")
    open(meta_path, "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=2))

    # Chek-list
    checklist = [
        "Proverit prava na muzyku/kartinki",
        "Sverit khronometrazh i subtitry",
        "Fill out end screens/cards (YouTube)",
        "Ukazat ssylku na Patreon/sayt",
        "Enable monetization (if available)"
    ]
    open(os.path.join(kit_dir, "upload_checklist.md"), "w", encoding="utf-8").write("# Upload Checklist\n\n" + "\n".join([f"- [ ] {x}" for x in checklist]) + "\n")

    # Instruktsii po upload
    instr = []
    if "youtube" in platform:
        instr = [
            "Zaydite na https://studio.youtube.com → Sozdat → Zagruzit video.",
            "Select a video file from this directory.",
            "Title/Description - from metadata.zsion. Tags are separated by commas.",
            "Subtitry → Zagruzit fayl → SRT, esli prisutstvuet.",
            "Thumbnail - select a thumbnail (if available)."
        ]
    elif platform == "tiktok":
        instr = [
            "Otkroyte https://www.tiktok.com/upload.",
            "Vyberite video. Zagolovok/kheshtegi — iz metadata.json.",
            "Opublikuyte v vertikalnom formate 9:16."
        ]
    elif platform == "patreon_post":
        instr = [
            "Zaydite na https://www.patreon.com/creator-home → Create → Post.",
            "Tip posta — Video/File (po situatsii).",
            "Zagolovok/tekst - iz metadata.json. Prilozhite video/audio, pri neobkhodimosti - SRT."
        ]
    elif platform == "instagram_reels":
        instr = [
            "Otkroyte Instagram app → + → Reel.",
            "Upload video. Caption - from metadata.zsion, add tags as #hashtags.",
            "Add subtitles manually or via app if CPT is available."
        ]
    open(os.path.join(kit_dir, "upload_instructions.md"), "w", encoding="utf-8").write("# Upload Instructions\n\n- " + "\n- ".join(instr) + "\n")

    # Kheshi
    hashes = {}
    for f in os.listdir(kit_dir):
        p = os.path.join(kit_dir, f)
        if os.path.isfile(p):
            hashes[f] = _sha256(p)
    open(os.path.join(kit_dir, "hashes.json"), "w", encoding="utf-8").write(json.dumps(hashes, ensure_ascii=False, indent=2))

    _mm_passport("Sobran upload-kit", {"platform": platform, "title": title, "kit_dir": kit_dir, "files": meta["files"]})
    return {"ok": True, "kit": kit_dir, "meta": meta, "hashes": hashes}

def list_kits() -> Dict[str, Any]:
    _ensure()
    items = []
    for d in sorted(os.listdir(OUT)):
        kdir = os.path.join(OUT, d)
        if os.path.isdir(kdir) and os.path.isfile(os.path.join(kdir, "metadata.json")):
            try:
                meta = json.load(open(os.path.join(kdir, "metadata.json"), "r", encoding="utf-8"))
                items.append({"dir": kdir, "platform": meta.get("platform"), "title": meta.get("title")})
            except Exception:
                pass
# return {"ok": True, "items": items}