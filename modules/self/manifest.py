# -*- coding: utf-8 -*-
"""
modules/self/manifest.py — samoopisanie vozmozhnostey i sostava Ester (SelfMap).

Mosty:
- Yavnyy: (Samosoznanie ↔ Memory) formiruet SelfMap i po zaprosu kladet ego v pamyat s «profileom».
- Skrytyy #1: (RAG ↔ Navigatsiya) karta prigodna dlya bystrykh otvetov «chto ya umeyu?».
- Skrytyy #2: (Bezopasnost ↔ Audit) fiksiruet versii i sha vazhnykh moduley.

Zemnoy abzats:
Kak karta organizma i navykov: chto est, gde lezhit, kakoy versii — i kogda obnovlyalos.

# c=a+b
"""
from __future__ import annotations
import os, json, time, importlib.util, hashlib
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

KEY_MODULES = [
    # yadro tekuschey sessii
    "modules.llm.broker",
    "modules.app.discover",
    "modules.volition.pulse",
    "modules.media.ingest",
    "modules.media.probe",
    "modules.media.outline",
    "modules.kg.linker",
    "modules.ops.cost_fence",
    "modules.resilience.rollback",
    "modules.self.forge",
    "modules.finance.sepa",
]

def _origin(mod: str) -> str:
    try:
        spec = importlib.util.find_spec(mod)
        if spec and spec.origin:
            return spec.origin
    except Exception:
        pass
    return ""

def _sha_file(path: str) -> str:
    if not path or not os.path.isfile(path): return ""
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def build_selfmap() -> Dict[str,Any]:
    ts=int(time.time())
    env = {
        "VOLITION_AB": os.getenv("VOLITION_AB","A"),
        "MEDIA_STT_ENGINE": os.getenv("MEDIA_STT_ENGINE","auto"),
        "LLM_DEFAULT_PROVIDER": os.getenv("LLM_DEFAULT_PROVIDER","lmstudio"),
    }
    modules=[]
    for m in KEY_MODULES:
        p=_origin(m)
        modules.append({"name": m, "origin": p, "sha256": _sha_file(p)})
    return {"ok": True, "selfmap": {"ts": ts, "env": env, "modules": modules}}

def store_selfmap() -> Dict[str,Any]:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
    except Exception:
        return {"ok": False, "error":"memory_unavailable"}
    rep=build_selfmap()
    if not rep.get("ok"): return rep
    sm=rep.get("selfmap") or {}
    mm=get_mm()
    text=json.dumps(sm, ensure_ascii=False, indent=2)
    meta={"kind":"selfmap","format":"json"}
    return upsert_with_passport(mm, text, meta, source="self://manifest")
# c=a+b