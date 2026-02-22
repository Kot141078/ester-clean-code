# -*- coding: utf-8 -*-
"""
modules/ops/summary.py — edinaya mashinnaya svodka sostoyaniya sistemy (JSON).

Mosty:
- Yavnyy: (Operatsii ↔ Mozg/Panel) daet bystryy snimok: LLM, volya, kvoty, media, KG, finansy i pr.
- Skrytyy #1: (Nadezhnost ↔ Fayly) chitaet statusy napryamuyu iz data/*, dazhe bez HTTP-ruchek.
- Skrytyy #2: (Samosoznanie ↔ Memory) mozhet byt sokhranen v pamyat cherez /self/manifest.

Zemnoy abzats:
Kak pribornaya panel avtomobilya: odnim vzglyadom vidno toplivo, temperaturu i lampochki.

# c=a+b
"""
from __future__ import annotations
import os, json, glob, shutil, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

EXTRA = os.getenv("OPS_SUMMARY_EXTRA","data/ops/summary_extra.json")

def _json_load(path: str, default: Any) -> Any:
    try:
        return json.load(open(path,"r",encoding="utf-8"))
    except Exception:
        return default

def _file_exists(path: str) -> bool:
    try:
        return os.path.isfile(path)
    except Exception:
        return False

def _tool(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None

def make_summary() -> Dict[str,Any]:
    now=int(time.time())
    out={
        "ts": now,
        "env": {
            "LLM_DEFAULT_PROVIDER": os.getenv("LLM_DEFAULT_PROVIDER","lmstudio"),
            "LMSTUDIO_BASE_URL": os.getenv("LMSTUDIO_BASE_URL","http://127.0.0.1:1234/v1"),
            "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL","http://127.0.0.1:11434"),
            "VOLITION_AB": os.getenv("VOLITION_AB","A"),
        },
        "tools": {
            "ffmpeg": _tool("ffmpeg"),
            "ffprobe": _tool("ffprobe"),
            "yt-dlp": _tool("yt-dlp"),
            "whisper": _tool("whisper"),
            "whisperx": _tool("whisperx"),
        },
        "llm": {},
        "volition": {},
        "ingest": {},
        "media": {},
        "kg": {},
        "memory": {},
        "finance": {},
        "security": {}
    }

    # LLM
    out["llm"]["openai_enabled"] = bool(os.getenv("OPENAI_API_KEY","").strip())
    out["llm"]["timeout_sec"] = int(os.getenv("LLM_TIMEOUT_SEC","30") or "30")

    # Volition
    vcfg = _json_load(os.getenv("VOLITION_CFG","data/volition/pulse.json"), {"tasks":[]})
    vlog_last=[]
    log_path=os.getenv("VOLITION_LOG","data/volition/log.jsonl")
    try:
        with open(log_path,"r",encoding="utf-8") as f:
            vlog_last=[json.loads(x) for x in f.readlines()[-20:]]
    except Exception:
        pass
    out["volition"]={"tasks": len(vcfg.get("tasks",[])), "recent": vlog_last}

    # Ingest quotas
    qdb=_json_load(os.getenv("INGEST_QUOTA_DB","data/ingest/quotas.json"), {"sources":{}})
    out["ingest"]=qdb

    # Media
    mdb=_json_load(os.getenv("MEDIA_DB","data/media/index.json"), {"items":{}})
    out["media"]={"count": len(mdb.get("items",{})), "root": os.getenv("MEDIA_ROOT","data/media/store")}

    # KG
    kg=_json_load(os.getenv("KG_DB","data/kg/graph.json"), {"nodes":{}, "edges":[]})
    out["kg"]={"nodes": len(kg.get("nodes",{})), "edges": len(kg.get("edges",[]))}

    # Memory (affect weights + health)
    weights=_json_load(os.getenv("AFFECT_WEIGHTS","data/mem/affect_weights.json"), {"weights":{}})
    out["memory"]={"affect_weights": len(weights.get("weights",{}))}
    health_touch=os.getenv("HEALTH_TOUCH","data/health/touch.txt")
    out["memory"]["health_touch_exists"]= _file_exists(health_touch)

    # Finance
    out_dir=os.getenv("FIN_OUT_DIR","data/finance/outgoing")
    fx=sorted(glob.glob(os.path.join(out_dir,"pain001_*.xml")))
    out["finance"]={"drafts": len(fx), "out_dir": out_dir}

    # Security
    pills=_json_load(os.getenv("PILL_DB","data/security/pills.json"), {"tokens":{}})
    roles=_json_load(os.getenv("RBAC_DB","data/security/roles.json"), {"roles":{}})
    out["security"]={"pills": len(pills.get("tokens",{})), "roles": roles.get("roles",{})}

    # Extras
    extras=_json_load(EXTRA, {})
    out["extra"]=extras

    return {"ok": True, "summary": out}
# c=a+b