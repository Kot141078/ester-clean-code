# -*- coding: utf-8 -*-
"""
modules/video/extractors/universal.py — «universalnyy» ekstraktor: metadannye, subtitry, chernovoy konspekt.
(obnovlennaya versiya: provaydery Vimeo/RuTube/generic cherez yt-dlp, saydkary, MKV-multitrek, yazykovye podskazki)

Funktsii:
  • fetch(req: dict) -> dict
     req: {"url"?: "...", "path"?: "...", "want":{"subs":true,"summary":true,"meta":true}, "topic"?: "...", "lang"?: "ru|en|..."}

Povedenie (A/B):
  • A — passthrough k probe (sovmestimost).  B — polnyy konveyer s avto-otkatom nazad pri oshibke.

Novoe:
  • Provaydery: YouTube/Vimeo/RuTube/generic cherez yt-dlp (meta+saby).
  • Lokalnye fayly: poisk saydkarov .srt/.vtt/.ass s uchetom yazyka, izvlechenie luchshey sab-dorozhki iz MKV.
  • ISO/DVD: bezopasnyy best-effort (bez montirovaniya).
  • Detektor yazyka pomogaet vybrat dorozhku/saydkar i otrazhaetsya v meta.

Mosty:
- Yavnyy: (Memory ↔ Video) unifitsirovannyy konspekt i subtitry dlya indeksirovaniya i RAG.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) A/B + avtootkat isklyuchayut regressii.
- Skrytyy #2: (Kibernetika ↔ Volya) rabotaet po zaprosu i po pravilam myshleniya, v t.ch. proaktivno.

Zemnoy abzats:
Eto «kombayn 2.0»: umeet brat saby iz Interneta, iz banki MKV, iz sosednego fayla; yazyk ugadyvaet sam i pishet profile.

# c=a+b

Ideya dlya rasshireniya: Integrirovat LLM-khuk dlya uluchsheniya summary (esli dostupen), naprimer, rezyumirovat subs_text cherez lokalnyy LLM.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from modules.video.metadata.ffprobe_ex import sys_capabilities, probe
from modules.video.subtitles.normalize import load_and_normalize, try_asr
from modules.video.subtitles.lang_detect import detect_lang, detect_lang_file
from modules.video.extractors.mkv_tools import extract_best_subs
from modules.video.extractors.iso_tools import is_dvd_folder, try_extract_dvd_subs
from modules.video.extractors.providers import classify_url, yt_info, yt_subs
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DATA_DIR = os.path.join(os.getcwd(), "data", "video_ingest")
os.makedirs(DATA_DIR, exist_ok=True)

FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
SUBS_SIDECAR_GLOB = bool(int(os.getenv("SUBS_SIDECAR_GLOB", "1")))
LANG_PREF = [s.strip() for s in os.getenv("MKV_EXTRACT_LANG_PREF", "ru,en").split(",") if s.strip()]

def _run(cmd: List[str], timeout: float = 120.0) -> tuple[int, str, str]:
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=timeout)
        return p.returncode or 0, out.decode("utf-8", "ignore"), err.decode("utf-8", "ignore")
    except Exception as e:
        return -1, "", str(e)

def _find_sidecars(path: str) -> List[str]:
    if not SUBS_SIDECAR_GLOB:
        return []
    try:
        base, _ = os.path.splitext(path)
        globs = [
            base + ".*.srt", base + ".*.vtt", base + ".*.ass",
            base + ".srt", base + ".vtt", base + ".ass",
        ]
        out = []
        for g in globs:
            out.extend(glob.glob(g))
        # unikaliziruem, samye «yazykovye» vyshe
        out = sorted(set(out), key=lambda p: (0 if re.search(r"\.(ru|eng|en|russian|rus)\.", p, re.I) else 1, p))
        return out
    except Exception:
        return []  # Dorabotka: ne padaem na oshibkakh puti

def _choose_sidecar(files: List[str], lang_hint: Optional[str]) -> Optional[str]:
    if not files:
        return None
    if lang_hint:
        for f in files:
            if re.search(rf"\.{re.escape(lang_hint)}(\.|$)", f, re.I):
                return f
    # esli est ru/en — predpochest, s sinonimami (dorabotka)
    for tag in ("ru", "rus", "russian", "en", "eng", "english"):
        for f in files:
            if re.search(rf"\.{tag}(\.|$)", f, re.I):
                return f
    return files[0]

def _draft_summary(title: str, desc: str, subs_text: str, limit: int = 1200) -> str:
    lines = []
    t = (title or "").strip()
    if t:
        lines.append(f"# {t}")
    d = (desc or "").strip()
    if d:
        lines.append(d[:400])
    if subs_text:
        subs_clean = re.sub(r"\[\[.+?\]\]\s*", "", subs_text)
        snippet = "\n".join(subs_clean.splitlines()[:30])
        lines.append(snippet)
    text = "\n\n".join([x for x in lines if x]).strip()
    return text[:limit]

def fetch(req: Dict[str, Any]) -> Dict[str, Any]:
    mode = (os.getenv("VIDEO_UNIVERSAL_AB", "A") or "A").upper()
    # esli A — delegirovat, esli est staryy konveyer
    if mode == "A":
        # pass-tru: vernem tolko probe + minimalist
        src = {"url": req.get("url")} if req.get("url") else {"path": req.get("path")}
        meta = probe(src)
        return {"ok": True, "mode": "A", "probe": meta, "note": "passthrough A (set VIDEO_UNIVERSAL_AB=B to enable universal extractor)"}

    # B-rezhim: polnyy tsikl
    try:
        url = (req.get("url") or "").strip()
        path = (req.get("path") or "").strip()
        want = req.get("want") or {"subs": True, "summary": True, "meta": True}
        lang = (req.get("lang") or "").strip() or None

        caps = sys_capabilities()
        rep: Dict[str, Any] = {"ok": True, "mode": "B", "source": {}, "meta": {}, "subs": {}, "summary": "", "capabilities": caps}

        subs_text: Optional[str] = None
        title = ""
        desc = ""
        subs_lang = "unknown"

        if url:
            rep["source"] = {"url": url}
            pclass = classify_url(url)
            info = yt_info(url)
            title = str(info.get("title") or "")
            desc = str(info.get("description") or "")
            rep["meta"]["provider"] = pclass
            rep["meta"]["yt_dlp"] = {k: info.get(k) for k in ("title", "uploader", "upload_date", "duration", "categories", "chapters", "tags") if k in info}
            if want.get("subs", True):
                vtt_path = yt_subs(url, lang)
                if vtt_path:
                    norm = load_and_normalize(vtt_path, fmt_hint="vtt", lang_hint=lang)
                    if norm.get("ok"):
                        subs_text = norm.get("text", "")
                        subs_lang = detect_lang(subs_text).get("lang", "unknown")  # type: ignore
                # chistim temp (iz pervoy versii)
                try:
                    d = os.path.join(DATA_DIR, "tmp_subs")
                    for f in os.listdir(d):
                        os.remove(os.path.join(d, f))
                except Exception:
                    pass
            rep["probe"] = probe({"url": url})
        elif path:
            rep["source"] = {"path": path}
            rep["probe"] = probe({"path": path})

            # 1) Saydkary ryadom
            sidecars = _find_sidecars(path)
            side = _choose_sidecar(sidecars, lang)
            if want.get("subs", True) and side:
                fmt = "vtt" if side.lower().endswith(".vtt") else "srt" if side.lower().endswith(".srt") else "ass"
                norm = load_and_normalize(side, fmt_hint=fmt, lang_hint=lang)
                if norm.get("ok"):
                    subs_text = norm.get("text", "")

            # 2) MKV vstroennye saby (esli net saydkara)
            if want.get("subs", True) and not subs_text and path.lower().endswith(".mkv"):
                best = extract_best_subs(path, LANG_PREF if LANG_PREF else (["ru", "en"]))
                if best:
                    norm = load_and_normalize(best, fmt_hint="srt", lang_hint=lang)
                    if norm.get("ok"):
                        subs_text = norm.get("text", "")

            # 3) DVD/ISO papka (best-effort)
            if want.get("subs", True) and not subs_text and is_dvd_folder(os.path.dirname(path) if os.path.isfile(path) else path):
                best = try_extract_dvd_subs(path, LANG_PREF if LANG_PREF else (["ru", "en"]))
                if best:
                    norm = load_and_normalize(best, fmt_hint="srt", lang_hint=lang)
                    if norm.get("ok"):
                        subs_text = norm.get("text", "")

            # 4) ASR pri polnom otsutstvii teksta i nalichii dvizhkov
            if want.get("subs", True) and not subs_text and (caps.get("python_whisper") or caps.get("python_faster_whisper")):
                # izvlechem audiodorozhku (16k mono)
                wav = os.path.join(DATA_DIR, f"asr_{int(time.time())}.wav")
                code, out, err = _run([FFMPEG, "-y", "-i", path, "-ac", "1", "-ar", "16000", "-vn", wav], timeout=180.0)
                if code == 0 and os.path.isfile(wav):
                    asr = try_asr(wav, model_hint="base")
                    if asr.get("ok"):
                        subs_text = asr.get("text")
                try:
                    os.remove(wav)
                except Exception:
                    pass

            # vychislim yazyk, esli smogli
            if subs_text:
                subs_lang = detect_lang(subs_text).get("lang", "unknown")  # type: ignore

        else:
            return {"ok": False, "error": "url or path required"}

        # Svodka/chernovik
        if want.get("summary", True):
            rep["summary"] = _draft_summary(title, desc, subs_text or "")

        if want.get("subs", True):
            rep["subs"] = {"ok": bool(subs_text), "text": subs_text or "", "lang": subs_lang}

        # Sokhranenie otcheta i best-effort vektorizatsiya
        ts = int(time.time())
        dump_path = os.path.join(DATA_DIR, f"rep_{ts}.json")
        rep_out = {
            "ts": ts,
            "source": rep.get("source"),
            "meta": rep.get("meta"),
            "probe": rep.get("probe"),
            "summary": rep.get("summary"),
            "transcript": {"ok": rep.get("subs", {}).get("ok"), "lang": subs_lang, "text": (subs_text or "")},
        }
        with open(dump_path, "w", encoding="utf-8") as f:
            json.dump(rep_out, f, ensure_ascii=False, indent=2)

        # Vektorizatsiya (best-effort)
        try:
            from modules.memory.vector_reconcile import reconcile  # type: ignore
            items = []
            if rep_out.get("summary"):
                items.append({"id": os.path.basename(dump_path) + "#sum", "text": rep_out["summary"], "tags": ["video", "summary"], "meta": {"src": rep.get("source"), "lang": subs_lang}})
            if (subs_text or "").strip():
                items.append({"id": os.path.basename(dump_path) + "#tr", "text": (subs_text or "")[:4000], "tags": ["video", "transcript"], "meta": {"src": rep.get("source"), "lang": subs_lang}})
            if items:
                reconcile(items)
        except Exception:
            pass

        return {"ok": True, "mode": "B", "dump": dump_path, "summary": rep.get("summary"),
                "subs_ok": rep.get("subs", {}).get("ok", False), "subs_lang": subs_lang}
    except Exception as e:
        # avtokatbek na A
        src = {"url": req.get("url")} if req.get("url") else {"path": req.get("path")}
        meta = probe(src)
# return {"ok": True, "mode": "A_fallback", "error": str(e), "probe": meta}