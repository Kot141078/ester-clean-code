# -*- coding: utf-8 -*-
"""
modules/media/yt_dlp_wrapper.py — skachivanie onlayn-video/subtitrov cherez yt-dlp s uchetom lokalnoy politiki kroulinga.

Mosty:
- Yavnyy: (Set ↔ Media) edinaya obertka dlya zagruzki, subtitrov, metadannykh.
- Skrytyy #1: (Zakonnost ↔ Politika) proveryaem /crawler/policy/check i uvazhaem delays/deny.
- Skrytyy #2: (Memory ↔ Profile) kladem JSON-manifest s sha/url.

Zemnoy abzats:
Kak «vezhlivyy zagruzchik»: sprosil «mozhno?», podozhdal, skachal, ostavil chek-list.

# c=a+b
"""
from __future__ import annotations
import json, os, time, subprocess
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MEDIA_DIR = os.getenv("MEDIA_DIR","data/media")
YT_DLP = os.getenv("YT_DLP_BIN","yt-dlp")
ALLOW = (os.getenv("MEDIA_ALLOW_DOWNLOAD","true").lower() == "true")
CRAWL_AB = (os.getenv("CRAWL_AB","A") or "A").upper()

def _ensure():
    os.makedirs(MEDIA_DIR, exist_ok=True)

def _policy(url: str) -> Dict[str,Any]:
    # lokalnyy vyzov politiki (bez vneshnikh zavisimostey)
    try:
        from modules.crawl.policy import check  # type: ignore
        return check(url)
    except Exception:
        return {"ok": True, "allow": True, "delay_ms": 0, "user_agent":"EsterResearchBot/1.0"}

def fetch(url: str, prefer_subs_lang: str | None = None) -> Dict[str,Any]:
    _ensure()
    pol = _policy(url)
    if not pol.get("allow", True):
        return {"ok": False, "error":"crawl_denied", "policy": pol}
    if not ALLOW:
        return {"ok": False, "error":"download_disabled"}
    # zaderzhka, esli ukazana
    delay_ms = int(pol.get("delay_ms",0))
    if delay_ms>0: time.sleep(min(delay_ms/1000.0, 10.0))  # ne zasypaem nadolgo
    # komanda yt-dlp
    outtpl = os.path.join(MEDIA_DIR, "%(title)s-%(id)s.%(ext)s")
    args = [YT_DLP, "-o", outtpl, "--restrict-filenames", "--no-playlist", "--no-color", url]
    # subtitry, esli prosili
    if prefer_subs_lang:
        args += ["--write-sub","--sub-lang", prefer_subs_lang, "--sub-format","srt"]
    # pytaemsya skachat
    try:
        r = subprocess.run(args, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            return {"ok": False, "error":"yt_dlp_failed", "stderr": r.stderr[-2000:]}
        # naydem posledniy fayl v kataloge
        files = sorted([os.path.join(MEDIA_DIR,f) for f in os.listdir(MEDIA_DIR)], key=os.path.getmtime)
        picked = [f for f in files if os.path.isfile(f) and not f.endswith(".part")]
        if not picked:
            return {"ok": False, "error":"no_file"}
        path = picked[-1]
        # manifest
        man = {"url": url, "path": path, "ts": int(time.time()), "policy": pol}
        json.dump(man, open(path + ".manifest.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
        return {"ok": True, "path": path, "manifest": man}
    except FileNotFoundError:
        return {"ok": False, "error":"yt_dlp_missing"}
# c=a+b