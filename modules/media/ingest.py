# -*- coding: utf-8 -*-
"""modules/media/ingest.py - oflayn/onlayn izvlechenie: metadannye, subtitry, chernovoy konspekt.

Mosty:
- Yavnyy: (Media ↔ Memory) kladem izvlechennoe v pamyat s profileom i KG-svyazyami.
- Skrytyy #1: (Inzheneriya ↔ Dostupnost) ffprobe/ffmpeg/yt-dlp ispolzuyutsya esli dostupny (best-effort).
- Skrytyy #2: (Kvoty ↔ Backpressure) pered tyazhelymi shagami spisyvaem tokeny ingest.
- Novoe: (Mesh/P2P ↔ Raspredelennost) sinkhronizatsiya indeksa media mezhdu agentami Ester.
- Novoe: (Cron ↔ Avtonomiya) ochistka starykh/redkikh zapisey dlya svezhesti BZ.
- Novoe: (Monitoring ↔ Prozrachnost) webhook na tyazhelye ingesty/oshibki dlya audita.

Zemnoy abzats:
Kak "multimediynyy pylesos" s setyu: uvideli fayl/URL - snyali metadannye, vytaschili subtitry/ASR, polozhili v pamyat, podelilis po P2P, pochistili po cron - i BZ Ester vsegda svezha, bez musora.

# c=a+b"""
from __future__ import annotations
import os, json, subprocess, tempfile, shlex, time, re, hashlib, shutil
from typing import Any, Dict, List
import urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MEDIA_AB = (os.getenv("MEDIA_AB", "A") or "A").upper()
MEDIA_DB = os.getenv("MEDIA_DB", "data/media/index.json")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "data/media/store")
OUTDIR = os.getenv("MEDIA_OUT", "data/media")  # legacy
YTDLP = os.getenv("YTDLP_BIN", "yt-dlp")
FFMPEG = os.getenv("FFMPEG_BIN", "ffmpeg")
FFPROBE = os.getenv("FFPROBE_BIN", "ffprobe")
STT_CMD = os.getenv("MEDIA_STT_CMD", "").strip()
STT_ENGINE = os.getenv("MEDIA_STT_ENGINE", "auto").lower()
LANGS = [x.strip() for x in (os.getenv("MEDIA_LANGS", "en,ru") or "en,ru").split(",") if x.strip()]
PEERS_STR = os.getenv("PEERS", "")  # "http://node1:port/sync,http://node2:port/sync"
PEERS = [p.strip() for p in PEERS_STR.split(",") if p.strip()]
CRON_MAX_AGE_DAYS = int(os.getenv("CRON_MAX_AGE_DAYS", "30") or "30")
MIN_SEEN = int(os.getenv("MIN_SEEN", "2") or "2")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
MONITOR_THRESHOLD = float(os.getenv("MONITOR_THRESHOLD", "5.0") or "5.0")

state: Dict[str, Any] = {"updated": 0, "items": {}, "last_cleanup": int(time.time())}

def _ensure():
    os.makedirs(MEDIA_ROOT, exist_ok=True)
    os.makedirs(os.path.dirname(MEDIA_DB), exist_ok=True)
    if not os.path.isfile(MEDIA_DB):
        json.dump({"items": {}}, open(MEDIA_DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load():
    global state
    _ensure()
    if os.path.isfile(MEDIA_DB):
        try:
            loaded = json.load(open(MEDIA_DB, "r", encoding="utf-8"))
            state["items"].update(loaded.get("items", {}))
            state["updated"] = loaded.get("updated", state["updated"])
            state["last_cleanup"] = loaded.get("last_cleanup", state["last_cleanup"])
        except Exception:
            pass
    # Sinkh ot peers pri starte
    if PEERS:
        for peer in PEERS:
            try:
                req = urllib.request.Request(f"{peer}", method="GET")
                with urllib.request.urlopen(req, timeout=5) as r:
                    peer_state = json.loads(r.read().decode("utf-8"))
                    for pid, data in peer_state.get("items", {}).items():
                        if pid not in state["items"] or data["created"] > state["items"][pid]["created"]:
                            state["items"][pid] = data
            except Exception:
                pass

def _save():
    state["updated"] = int(time.time())
    json.dump({"items": state["items"]}, open(MEDIA_DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    sync_with_peers()

def sync_with_peers():
    if not PEERS:
        return
    body = json.dumps({"items": state["items"]}).encode("utf-8")
    for peer in PEERS:
        try:
            req = urllib.request.Request(f"{peer}", data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

def receive_sync(payload: Dict[str, Any]):
    _load()
    for pid, data in payload.get("items", {}).items():
        if pid not in state["items"] or data["created"] > state["items"][pid]["created"]:
            state["items"][pid] = data
    _save()

def _is_url(s: str) -> bool:
    return bool(re.match(r"^(https?://|rtmp://|rts?://|mms://)", s or "", re.I))

def _run(cmd: List[str], timeout: int = 120) -> Dict[str, Any]:
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = p.communicate(timeout=timeout)
        return {"ok": p.returncode == 0, "out": out, "err": err, "rc": p.returncode}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _cmd_exists(x: str) -> bool:
    return shutil.which(x) is not None

def _consume(cost: float) -> bool:
    try:
        from modules.ingest.guard import check_and_consume  # type: ignore
        rep = check_and_consume("media", int(cost))
        return bool(rep.get("allowed", True))
    except Exception:
        return True

def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _ytdlp(url: str, outdir: str, want_subs: bool) -> Dict[str, Any]:
    if not _cmd_exists(YTDLP):
        return {"ok": False, "error": "yt-dlp_missing"}
    cmd = [YTDLP, "-o", os.path.join(outdir, "%(id)s.%(ext)s"), "--restrict-filenames", "--no-call-home", "--no-warnings"]
    if want_subs:
        cmd += ["--write-sub", "--write-auto-sub", "--sub-lang", ",".join(LANGS)]
    cmd += ["-f", "bestvideo+bestaudio/best", url]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate(timeout=21600)
    ok = (p.returncode == 0)
    return {"ok": ok, "stdout": out, "stderr": err}

def _ffmpeg_audio(src: str, dst: str) -> Dict[str, Any]:
    if not _cmd_exists(FFMPEG):
        return {"ok": False, "error": "ffmpeg_missing"}
    cmd = [FFMPEG, "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", dst]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate(timeout=21600)
    return {"ok": p.returncode == 0, "stderr": err}

def _run_stt(audio_path: str, out_base: str) -> Dict[str, Any]:
    if STT_ENGINE == "none":
        return {"ok": True, "note": "stt_disabled"}
    # auto: whisperx > whisper > cmd > none
    if STT_ENGINE in ("auto", "whisperx") and _cmd_exists("whisperx"):
        cmd = ["whisperx", audio_path, "--language", "auto", "--output_format", "vtt", "--output_dir", os.path.dirname(out_base)]
        rep = _run(cmd, 600)
        vtt = os.path.join(os.path.dirname(out_base), "audio.vtt")  # whisperx output
        if rep["ok"] and os.path.isfile(vtt):
            shutil.move(vtt, out_base + ".vtt")
            return {"ok": True, "vtt": out_base + ".vtt"}
    if STT_ENGINE in ("auto", "whisper") and _cmd_exists("whisper"):
        cmd = ["whisper", audio_path, "--language", "auto", "--output_format", "vtt", "--output_dir", os.path.dirname(out_base)]
        rep = _run(cmd, 600)
        vtt = os.path.join(os.path.dirname(out_base), os.path.basename(audio_path).rsplit(".", 1)[0] + ".vtt")
        if rep["ok"] and os.path.isfile(vtt):
            shutil.move(vtt, out_base + ".vtt")
            return {"ok": True, "vtt": out_base + ".vtt"}
    if STT_CMD:
        cmd = shlex.split(STT_CMD) + [audio_path, out_base + ".vtt"]
        rep = _run(cmd, 600)
        if rep["ok"] and os.path.isfile(out_base + ".vtt"):
            return {"ok": True, "vtt": out_base + ".vtt"}
    return {"ok": False, "error": "stt_failed"}

def _ffprobe(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"ok": False, "error": "not_found"}
    cmd = [FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]
    rep = _run(cmd, 60)
    if rep["ok"]:
        try:
            return {"ok": True, **json.loads(rep["out"] or "{}")}
        except Exception:
            return {"ok": True, "raw": rep["out"]}
    return rep

def _extract_subs_local(path: str, out_base: str) -> List[str]:
    subs = []
    for i in range(10):
        srt = f"{out_base}.sub{i}.srt"
        cmd = [FFMPEG, "-y", "-i", path, "-map", f"0:s:{i}", "-c:s", "srt", srt]
        rep = _run(cmd, 120)
        if rep["ok"] and os.path.isfile(srt) and os.path.getsize(srt) > 0:
            subs.append(srt)
        else:
            if i > 0:
                break
    return subs

def _extract_audio(path: str, out_wav: str) -> Dict[str, Any]:
    return _ffmpeg_audio(path, out_wav)

def _upsert_memory(text: str, source: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from modules.mem.passport import upsert_with_passport  # type: ignore
        from services.mm_access import get_mm  # type: ignore
        mm = get_mm()
        return upsert_with_passport(mm, text, meta, source)
    except Exception as e:
        return {"ok": False, "error": f"memory:{e}"}

def _kg_link(text: str, sha: str) -> Dict[str, Any]:
    try:
        from modules.kg.linker import extract, upsert_to_kg  # type: ignore
        ents = extract(text or "").get("entities", {})
        return upsert_to_kg(ents, sha)
    except Exception:
        return {"ok": True, "note": "kg_optional"}

def cron_cleanup():
    _load()
    now = int(time.time())
    if now - state["last_cleanup"] >= 86400:  # daily
        to_remove = []
        for pid, data in state["items"].items():
            age_days = (now - data.get("created", now)) / 86400
            seen = data.get("seen", 0)
            if age_days > CRON_MAX_AGE_DAYS or seen < MIN_SEEN:
                to_remove.append(pid)
                # We delete files in the mouth
                root = data.get("root")
                if root and os.path.isdir(root):
                    shutil.rmtree(root, ignore_errors=True)
        for pid in to_remove:
            del state["items"][pid]
        state["last_cleanup"] = now
        _save()
    return {"ok": True, "cleanup_time": state["last_cleanup"], "removed": len(to_remove)}

def media_ingest(path_or_url: str, want_subtitles: bool = True, want_stt: bool = False, want_outline: bool = False, tags: List[str] | None = None) -> Dict[str, Any]:
    _load()
    cron_cleanup()
    rep = {"ok": True, "path_or_url": path_or_url}
    is_url = _is_url(path_or_url)
    pid = _sha(path_or_url)
    root = os.path.join(MEDIA_ROOT, pid)
    os.makedirs(root, exist_ok=True)
    item = {"id": pid, "url": path_or_url if is_url else None, "file": path_or_url if not is_url else None, "root": root, "created": int(time.time()),
            "tags": list(tags or []), "subs": [], "transcript": None, "meta": {}, "seen": 0}
    # Kvoty
    cost = 5.0 if is_url else 2.0  # uslovno
    if not _consume(cost):
        return {"ok": False, "error": "quota_exceeded"}
    # Skachat/kopirovat
    if is_url:
        dl = _ytdlp(path_or_url, root, want_subtitles)
        item["meta"]["ytdlp"] = dl
        if not dl["ok"]:
            rep["error"] = dl["error"]
            return rep
    else:
        if os.path.isfile(path_or_url):
            base = os.path.join(root, os.path.basename(path_or_url))
            if not os.path.isfile(base):
                shutil.copy2(path_or_url, base)
            item["meta"]["local_copy"] = base
    # Probing
    media_file = next((os.path.join(root, fn) for fn in os.listdir(root) if fn.lower().endswith((".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".wav", ".mov", ".avi"))), None)
    if media_file:
        probe = _ffprobe(media_file)
        rep["probe"] = probe
    # Subs
    subs = []
    if want_subtitles:
        if not is_url:
            subs = _extract_subs_local(path_or_url if not is_url else media_file, os.path.join(root, "subs"))
        else:
            for fn in os.listdir(root):
                if fn.lower().endswith((".vtt", ".srt", ".ass", ".sbv")):
                    subs.append(os.path.join(root, fn))
    item["subs"] = subs
    # STT if necessary
    if (not subs or want_stt) and media_file:
        out_wav = os.path.join(root, "audio.wav")
        if _extract_audio(media_file, out_wav)["ok"]:
            stt = _run_stt(out_wav, os.path.join(root, "stt"))
            if stt.get("ok") and os.path.isfile(os.path.join(root, "stt.vtt")):
                subs.append(os.path.join(root, "stt.vtt"))
                item["subs"] = subs
                item["meta"]["stt"] = "ok"
            else:
                item["meta"]["stt"] = "fail"
            rep["stt"] = stt
    # Tekst iz subs
    text = ""
    if subs:
        try:
            from modules.media.subs import parse_subtitles  # type: ignore
            acc = []
            for sp in subs:
                sub_rep = parse_subtitles(sp)
                if sub_rep.get("ok"):
                    acc.append(sub_rep.get("text", ""))
            text = " ".join(acc)
            item["transcript"] = os.path.join(root, "transcript.txt")
            with open(item["transcript"], "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass
    rep["draft_len"] = len(text)
    # Utline if shrouds
    outline = {}
    if want_outline and text:
        try:
            from modules.media.outline import build_outline  # type: ignore
            from modules.mem.passport import sha256_text  # type: ignore
            prov = {"sha256": sha256_text(text), "media_id": pid}
            outline = build_outline(text, title=os.path.basename(path_or_url), to_memory=True, provenance=prov)
            if outline.get("outline"):
                with open(os.path.join(root, "outline.md"), "w", encoding="utf-8") as f:
                    f.write(outline["outline"])
        except Exception:
            pass
    rep["outline"] = outline
    # Memory + KG
    if text:
        m = _upsert_memory(text, f"media://{path_or_url}", {"tags": item["tags"], "media_files": subs + [item["transcript"]], "provenance": {"sha256": _sha(text)}})
        rep["memory"] = m
        sha = ((m.get("provenance") or {}).get("sha256") or "")
        if sha:
            rep["kg"] = _kg_link(text, sha)
    # Webhook if heavy
    if WEBHOOK_URL and cost > MONITOR_THRESHOLD:
        try:
            alert = {"id": pid, "cost": cost, "len": len(text), "ts": int(time.time())}
            body = json.dumps(alert).encode("utf-8")
            req = urllib.request.Request(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    # Save item, incr seen
    state["items"][pid] = item
    state["items"][pid]["seen"] = state["items"][pid].get("seen", 0) + 1
    _save()
    try:
        from modules.mem.passport import append as _pp
        _pp("media_ingest", {"id": pid, "cost": cost, "len": len(text)}, "media://ingest")
    except Exception:
        pass
    rep["id"] = pid
    rep["root"] = root
    rep["subs"] = subs
    rep["transcript"] = item["transcript"]
    rep["files"] = subs + [item["transcript"]]
# return rep



