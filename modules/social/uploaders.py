# -*- coding: utf-8 -*-
"""modules/social/uploaders.py - publikatsiya kit'ov: manual (instruktsii) i api (pri nalichii klyuchey), zhurnal.

Mosty:
- Yavnyy: (Kit ↔ Publikatsiya) pytaetsya otpravit cherez API or generate manual-instruktsii.
- Skrytyy #1: (Zhurnal ↔ Uchet) zapisyvaet fakt publikatsii i id/ssylku.
- Skrytyy #2: (RBAC ↔ Ostorozhnost) predpolagaetsya vyzov cherez zaschischennye ruchki.

Zemnoy abzats:
Kak “kurer”: esli est propusk - zanosit pryamo v zdanie; esli net - ostavlyaet akkuratnyy paket i podrobnuyu zapisku, where nesti.

# c=a+b"""
from __future__ import annotations
import os, json, time, glob, urllib.request, urllib.error
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MODE=os.getenv("SOCIAL_UPLOAD_MODE","manual").lower()
ROOT=os.getenv("SOCIAL_OUT","data/social/kits")
YT=os.getenv("YT_API_KEY","").strip()
TT=os.getenv("TIKTOK_API_KEY","").strip()
PT=os.getenv("PATREON_TOKEN","").strip()

LEDGER_DB="data/social/ledger.json"

def _ensure():
    os.makedirs(os.path.dirname(LEDGER_DB), exist_ok=True)
    if not os.path.isfile(LEDGER_DB):
        json.dump({"posts":[]}, open(LEDGER_DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _ledger_add(rec: Dict[str,Any])->None:
    _ensure()
    j=json.load(open(LEDGER_DB,"r",encoding="utf-8"))
    j["posts"].append(rec)
    json.dump(j, open(LEDGER_DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def creds_status()->Dict[str,Any]:
    return {"ok": True, "mode": MODE, "providers": {"youtube": bool(YT), "tiktok": bool(TT), "patreon": bool(PT)}}

def _read_meta(kdir: str)->Dict[str,Any]:
    return json.load(open(os.path.join(kdir,"meta.json"),"r",encoding="utf-8"))

def _passport(note: str, meta: Dict[str,Any])->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="social://upload")
    except Exception:
        pass

def _api_try(url: str, method: str="POST", headers: Dict[str,str]|None=None, body: Dict[str,Any]|None=None)->Dict[str,Any]:
    data=json.dumps(body or {}).encode("utf-8") if body is not None else None
    req=urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return {"ok": True, "code": r.getcode(), "body": json.loads(r.read().decode("utf-8")) if "application/json" in (r.headers.get("Content-Type") or "") else {}}
    except urllib.error.HTTPError as e:
        return {"ok": False, "code": e.code, "error": e.read().decode("utf-8",errors="ignore")}
    except Exception as e:
        return {"ok": False, "code": 0, "error": str(e)}

def _upload_youtube(kdir: str)->Dict[str,Any]:
    # Real APIs require OAuth; We will support the “manual” completely and the “api” placeholder.
    meta=_read_meta(kdir)
    if MODE!="api" or not YT:
        rec={"ok": True, "mode":"manual", "note":"Use YouTube Studio as per upload_instructions.md"}
        _ledger_add({"ts": int(time.time()), "platform":"youtube", "title": meta.get("title",""), "mode":"manual", "dir": kdir})
        _passport("social_upload", {"platform":"youtube","mode":"manual","dir":kdir})
        return rec
    # Pseudo-request (fail offline), but we fake it
    rep=_api_try("https://www.googleapis.com/youtube/v3/videos?part=snippet&key="+YT, "POST", {"Content-Type":"application/json"}, {"snippet":{"title":meta.get("title","")}})
    if not rep.get("ok"):
        _ledger_add({"ts": int(time.time()), "platform":"youtube", "title": meta.get("title",""), "mode":"api-fallback", "dir": kdir, "error": rep.get("error","")})
        _passport("social_upload", {"platform":"youtube","mode":"api-fallback","dir":kdir,"error": rep.get("error","")})
        return {"ok": True, "mode":"api-fallback", "note":"Fell back to manual. See upload_instructions.md"}
    vid = (rep.get("body") or {}).get("id","")
    _ledger_add({"ts": int(time.time()), "platform":"youtube", "title": meta.get("title",""), "mode":"api", "dir": kdir, "id": vid})
    _passport("social_upload", {"platform":"youtube","mode":"api","dir":kdir,"id":vid})
    return {"ok": True, "mode":"api", "id": vid}

def _upload_tiktok(kdir: str)->Dict[str,Any]:
    meta=_read_meta(kdir)
    if MODE!="api" or not TT:
        _ledger_add({"ts": int(time.time()), "platform":"tiktok", "title": meta.get("title",""), "mode":"manual", "dir": kdir})
        _passport("social_upload", {"platform":"tiktok","mode":"manual","dir":kdir})
        return {"ok": True, "mode":"manual"}
    rep=_api_try("https://open.tiktokapis.com/v2/video/upload/","POST",{"Authorization":"Bearer "+TT,"Content-Type":"application/json"},{"title": meta.get("title","")})
    if not rep.get("ok"):
        _ledger_add({"ts": int(time.time()), "platform":"tiktok", "title": meta.get("title",""), "mode":"api-fallback", "dir": kdir, "error": rep.get("error","")})
        _passport("social_upload", {"platform":"tiktok","mode":"api-fallback","dir":kdir,"error": rep.get("error","")})
        return {"ok": True, "mode":"api-fallback"}
    pid=(rep.get("body") or {}).get("id","")
    _ledger_add({"ts": int(time.time()), "platform":"tiktok", "title": meta.get("title",""), "mode":"api", "dir": kdir, "id": pid})
    _passport("social_upload", {"platform":"tiktok","mode":"api","dir":kdir,"id":pid})
    return {"ok": True, "mode":"api", "id": pid}

def _upload_patreon(kdir: str)->Dict[str,Any]:
    meta=_read_meta(kdir)
    if MODE!="api" or not PT:
        _ledger_add({"ts": int(time.time()), "platform":"patreon", "title": meta.get("title",""), "mode":"manual", "dir": kdir})
        _passport("social_upload", {"platform":"patreon","mode":"manual","dir":kdir})
        return {"ok": True, "mode":"manual"}
    rep=_api_try("https://www.patreon.com/api/posts","POST",{"Authorization":"Bearer "+PT,"Content-Type":"application/json"},{"title": meta.get("title",""), "content": meta.get("description","")})
    if not rep.get("ok"):
        _ledger_add({"ts": int(time.time()), "platform":"patreon", "title": meta.get("title",""), "mode":"api-fallback", "dir": kdir, "error": rep.get("error","")})
        _passport("social_upload", {"platform":"patreon","mode":"api-fallback","dir":kdir,"error": rep.get("error","")})
        return {"ok": True, "mode":"api-fallback"}
    pid=(rep.get("body") or {}).get("id","")
    _ledger_add({"ts": int(time.time()), "platform":"patreon", "title": meta.get("title",""), "mode":"api", "dir": kdir, "id": pid})
    _passport("social_upload", {"platform":"patreon","mode":"api","dir":kdir,"id":pid})
    return {"ok": True, "mode":"api", "id": pid}

def upload(platform: str, kit_dir: str)->Dict[str,Any]:
    if platform=="youtube": return _upload_youtube(kit_dir)
    if platform=="tiktok":  return _upload_tiktok(kit_dir)
    if platform=="patreon": return _upload_patreon(kit_dir)
    return {"ok": False, "error":"unknown_platform"}

def ledger_list()->Dict[str,Any]:
    _ensure()
    j=json.load(open(LEDGER_DB,"r",encoding="utf-8"))
    return {"ok": True, "posts": j.get("posts",[])}
# c=a+b