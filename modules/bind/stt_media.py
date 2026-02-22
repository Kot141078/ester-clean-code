# -*- coding: utf-8 -*-
"""
modules/bind/stt_media.py — binder «media → transkript»: idem po MEDIA_INDEX, gde net teksta — zovem STT.

Mosty:
- Yavnyy: (Media ↔ STT) avtomatiziruet sozdanie subtitrov dlya novykh video/audio.
- Skrytyy #1: (Profile ↔ Prozrachnost) fiksiruem zapuski i naydennye/obrabotannye elementy.
- Skrytyy #2: (RAG/KG ↔ Bogache kontekst) gotovye teksty srazu popadayut v poisk.

Zemnoy abzats:
Kak konveyer podrezki: novye roliki poluchili — srazu sdelali im tekst i taymkody.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MEDIA_INDEX=os.getenv("MEDIA_INDEX","data/media/index.json")
STT_DIR=os.getenv("STT_DIR","data/stt")
STATE="data/bind/stt_state.json"
os.makedirs(os.path.dirname(STATE), exist_ok=True)

def _read_index()->list[dict]:
    try:
        j=json.load(open(MEDIA_INDEX,"r",encoding="utf-8"))
        return list(j.get("items") or [])
    except Exception:
        return []

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "bind://stt")
    except Exception:
        pass

def _state()->dict:
    if not os.path.isfile(STATE):
        json.dump({"runs":0,"processed":{}}, open(STATE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return json.load(open(STATE,"r",encoding="utf-8"))

def status()->dict:
    st=_state()
    try:
        seen=len(st.get("processed") or {})
    except Exception:
        seen=0
    return {"ok": True, "runs": int(st.get("runs",0)), "seen": seen, "media_index": MEDIA_INDEX}

def run()->dict:
    items=_read_index()
    st=_state(); proc=st.get("processed") or {}
    done=0; total=0; acc=[]
    for it in items:
        total+=1
        mid=str(it.get("id",""))
        paths=it.get("paths") or {}
        src=paths.get("file") or paths.get("audio") or paths.get("video")
        if not src or not os.path.isfile(src):
            continue
        if proc.get(mid):
            continue
        # esli uzhe est notes v kartochke — propustim
        if paths.get("notes") and os.path.isfile(paths["notes"]):
            proc[mid]={"t": int(time.time()), "skip":"has_notes"}; continue
        # vyzov STT
        try:
            from modules.audio.stt import transcribe  # type: ignore
            rep=transcribe(src, None, os.path.join(STT_DIR, mid))
            if rep.get("ok"):
                proc[mid]={"t": int(time.time()), "id": rep.get("id")}
                done+=1; acc.append({"media_id": mid, "stt_id": rep.get("id")})
        except Exception:
            proc[mid]={"t": int(time.time()), "err":"stt_failed"}
    st["processed"]=proc; st["runs"]=int(st.get("runs",0))+1
    json.dump(st, open(STATE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    _passport("bind_stt_run", {"total": total, "done": done})
    return {"ok": True, "total": total, "done": done, "linked": acc}
# c=a+b