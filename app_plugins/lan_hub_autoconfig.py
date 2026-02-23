# -*- coding: utf-8 -*-
"""Avtokonfig LAN-khaba (Windows). Sm. README v pakete.
AB-slot: ESTER_LANHUB_AB (A=vykl, B=vkl).
"""
from __future__ import annotations
import os, platform, subprocess
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _bool(name:str, default:bool)->bool:
    v = os.getenv(name)
    if v is None: return default
    return str(v).strip().lower() in ("1","true","yes","on","b")

def _log(line:str):
    try:
        os.makedirs("data", exist_ok=True)
        with open(os.path.join("data","bringup_diag.log"), "a", encoding="utf-8") as f:
            f.write(line.rstrip()+"\n")
    except Exception:
        pass

def _candidate_hub_path()->str:
    drive = os.getenv("ESTER_LANHUB_DRIVE", "Z").strip(": ").upper()
    subdir = os.getenv("ESTER_LANHUB_DIR", "ester-data").strip("\/ ")
    return f"{drive}:\\{subdir}"

def _try_automap()->None:
    unc = os.getenv("ESTER_LANHUB_UNC","").strip()
    drive = os.getenv("ESTER_LANHUB_DRIVE","Z").strip(": ").upper()+":"
    opts = os.getenv("ESTER_LANHUB_NETUSE_OPTS", "/persistent:yes")
    if not unc or platform.system().lower() != "windows":
        return
    try:
        subprocess.run(["net","use",drive,"/delete","/y"], check=False, capture_output=True)
        cmd = ["net","use",drive,unc] + opts.split()
        subprocess.run(cmd, check=True, capture_output=True)
        _log(f"[lanhub] net use success: {drive} -> {unc}")
    except Exception as e:
        _log(f"[lanhub] net use failed: {e!r}")

def _exists_dir(p:str)->bool:
    try: return os.path.isdir(p)
    except Exception: return False

def _ensure_dir(p:str)->None:
    try: os.makedirs(p, exist_ok=True)
    except Exception: pass

def register(app):
    if os.getenv("ESTER_LANHUB_AB","A").upper() != "B":
        _log("[lanhub] disabled (ESTER_LANHUB_AB!=B)")
        return

    hub_path = _candidate_hub_path()
    prefer_local = _bool("ESTER_LANHUB_FORCE_LOCAL", False)
    allow_override = _bool("ESTER_LANHUB_ALLOW_OVERRIDE", True)
    automap = _bool("ESTER_LANHUB_AUTOMAP", False)

    if automap and not _exists_dir(hub_path):
        _try_automap()

    using_hub = _exists_dir(hub_path) and not prefer_local
    current_root = os.getenv("ESTER_DATA_ROOT")

    if using_hub and allow_override:
        os.environ["ESTER_DATA_ROOT"] = hub_path
        _ensure_dir(os.path.join(hub_path, "memory"))
        _ensure_dir(os.path.join(hub_path, "logs"))
        _log(f"[lanhub] using hub: ESTER_DATA_ROOT={hub_path}")
    elif not current_root:
        os.environ["ESTER_DATA_ROOT"] = os.path.join(os.getcwd(), "data")
        _ensure_dir(os.environ["ESTER_DATA_ROOT"])
        _log(f"[lanhub] using local fallback: ESTER_DATA_ROOT={os.environ['ESTER_DATA_ROOT']}")
    else:
        _log(f"[lanhub] keep pre-set ESTER_DATA_ROOT={current_root} (hub_exists={_exists_dir(hub_path)})")

    try:
        app.config["LANHUB_STATUS"] = dict(
            ab=os.getenv("ESTER_LANHUB_AB","A").upper(),
            hub_path=hub_path,
            hub_exists=_exists_dir(hub_path),
            using_hub=using_hub and allow_override,
            data_root=os.getenv("ESTER_DATA_ROOT"),
            automap=automap,
            allow_override=allow_override,
            prefer_local=prefer_local,
        )
    except Exception:
        pass
# c=a+b