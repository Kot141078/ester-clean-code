# -*- coding: utf-8 -*-
"""
modules/thinking/act_guard.py — storozh deystviy myshleniya: skhema/timeout/WIP/denylist.

Mosty:
- Yavnyy: (Mysli ↔ Bezopasnost) tsentralizovannyy kontrol zapuska ekshenov (limity, taymauty, denylist).
- Skrytyy #1: (Ekonomika ↔ Nadezhnost) predotvraschaet zavisaniya i peregruzku uzla.
- Skrytyy #2: (Reestr ↔ Prozrachnost) khranit metadannye, schetchiki, zhurnal poslednikh zapuskov.

Zemnoy abzats:
Eto «dispetcher» v tsekhe: ne daet zapuskat lishnee, sledit za kolichestvom parallelnykh rabot i gasit zavisshie.

# c=a+b
"""
from __future__ import annotations
import os, json, time, threading
from typing import Any, Dict, Callable
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("ACT_GUARD_AB","A") or "A").upper()
DB = os.getenv("ACT_GUARD_DB","data/thinking/act_guard.json")
WIP_DEF = int(os.getenv("ACT_GUARD_WIP_DEFAULT","4") or "4")
TO_DEF  = int(os.getenv("ACT_GUARD_TIMEOUT_DEFAULT","30") or "30")
DENY    = set([x.strip() for x in (os.getenv("ACT_GUARD_DENYLIST","") or "").split(",") if x.strip()])

_LOCK = threading.RLock()
_REG: Dict[str, Dict[str,Any]] = {}      # name -> {func, schema_in, schema_out, wip, timeout, enabled, stats}
_WIP: Dict[str, int] = {}                # name -> current WIP

def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store  # type: ignore
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"actions":{}, "last_runs":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _safe_int(v: Any, default: int, min_value: int = 0) -> int:
    try:
        out = int(v)
    except Exception:
        out = int(default)
    if out < int(min_value):
        out = int(min_value)
    return out

def _passport(note: str, meta: Dict[str,Any])->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="think://guard")
    except Exception:
        pass

def hook_register():
    """
    Podklyuchaetsya poverkh suschestvuyuschego modules.thinking.action_registry (esli est).
    Sovmestim so starymi i novymi signaturami register(...).
    """
    try:
        import modules.thinking.action_registry as ar  # type: ignore
    except Exception:
        return False
    if hasattr(ar, "_guard_wrapped"):  # uzhe podklyucheny
        return True

    orig_reg = getattr(ar, "register", None)
    if not callable(orig_reg):
        return False

    def wrapped_register(*args, **kwargs):
        name = str(kwargs.get("kind") or kwargs.get("name") or (args[0] if len(args) >= 1 else "")).strip()
        if not name:
            return orig_reg(*args, **kwargs)

        in_schema = kwargs.get("inputs")
        if in_schema is None:
            in_schema = kwargs.get("in_schema")
        if in_schema is None and len(args) >= 2:
            in_schema = args[1]

        out_schema = kwargs.get("outputs")
        if out_schema is None:
            out_schema = kwargs.get("out_schema")
        if out_schema is None and len(args) >= 3:
            out_schema = args[2]

        legacy_shape = (
            len(args) >= 5
            and callable(args[4])
            and len(args) < 6
            and "fn" not in kwargs
            and "timeout_sec" not in kwargs
            and "concurrency" not in kwargs
        )

        timeout = TO_DEF
        wip = WIP_DEF
        cost = 0
        func = None

        if legacy_shape:
            cost = _safe_int(args[3] if len(args) >= 4 else kwargs.get("cost"), 0, 0)
            func = args[4]
        else:
            timeout_raw = kwargs.get("timeout_sec")
            if timeout_raw is None and len(args) >= 4 and not callable(args[3]):
                timeout_raw = args[3]
            timeout = _safe_int(timeout_raw, TO_DEF, 1)

            wip_raw = kwargs.get("concurrency")
            if wip_raw is None and len(args) >= 5 and not callable(args[4]):
                wip_raw = args[4]
            wip = _safe_int(wip_raw, WIP_DEF, 1)

            cost = _safe_int(timeout, 0, 0)
            fn_kw = kwargs.get("fn")
            if callable(fn_kw):
                func = fn_kw
            elif callable(kwargs.get("func")):
                func = kwargs.get("func")
            elif len(args) >= 6 and callable(args[5]):
                func = args[5]
            elif len(args) >= 5 and callable(args[4]):
                func = args[4]
            elif len(args) >= 4 and callable(args[3]):
                func = args[3]

        with _LOCK:
            _REG[name] = {
                "func": func,
                "in": dict(in_schema) if isinstance(in_schema, dict) else {},
                "out": dict(out_schema) if isinstance(out_schema, dict) else {},
                "wip": wip,
                "timeout": timeout,
                "enabled": True,
                "cost": cost,
                "stats": {"ok":0,"fail":0,"timeout":0}
            }
        return orig_reg(*args, **kwargs)

    ar.register = wrapped_register  # type: ignore
    ar._guard_wrapped = True        # type: ignore
    return True

def set_config(name: str, timeout: int|None=None, wip: int|None=None, enabled: bool|None=None)->Dict[str,Any]:
    with _LOCK:
        if name not in _REG:
            _REG[name] = {"func": None, "in":{}, "out":{}, "wip": WIP_DEF, "timeout": TO_DEF, "enabled": True, "cost": 0, "stats":{"ok":0,"fail":0,"timeout":0}}
        if timeout is not None: _REG[name]["timeout"]=int(timeout)
        if wip     is not None: _REG[name]["wip"]=max(1,int(wip))
        if enabled is not None: _REG[name]["enabled"]=bool(enabled)
        j=_load(); j["actions"][name]= {"timeout": _REG[name]["timeout"], "wip": _REG[name]["wip"], "enabled": _REG[name]["enabled"]}; _save(j)
    return {"ok": True, "name": name, "cfg": j["actions"][name]}

def status()->Dict[str,Any]:
    with _LOCK:
        j=_load()
        reg={k: {kk:v for kk,v in vv.items() if kk in ("wip","timeout","enabled","cost","stats")} for k,vv in _REG.items()}
        return {"ok": True, "ab": AB, "deny": list(DENY), "registry": reg, "persist": j.get("actions",{}), "wip": dict(_WIP)}

def _inc(name:str): _WIP[name]=_WIP.get(name,0)+1
def _dec(name:str): _WIP[name]=max(0,_WIP.get(name,0)-1)

def run(name: str, args: Dict[str,Any]|None=None)->Dict[str,Any]:
    args=dict(args or {})
    with _LOCK:
        info=_REG.get(name, {"func": None, "wip": WIP_DEF, "timeout": TO_DEF, "enabled": True})
        func=info.get("func")
        wip_max=int(info.get("wip",WIP_DEF))
        timeout=int(info.get("timeout",TO_DEF))
        enabled=bool(info.get("enabled", True))
    if name in DENY:
        try:
            _mirror_background_event(
                f"[ACT_GUARD_DENY] {name}",
                "act_guard",
                "deny",
            )
        except Exception:
            pass
        return {"ok": False, "error":"denied_by_env"}
    if not enabled and AB=="A":
        try:
            _mirror_background_event(
                f"[ACT_GUARD_DISABLED] {name}",
                "act_guard",
                "disabled",
            )
        except Exception:
            pass
        return {"ok": False, "error":"disabled"}
    if AB=="A" and _WIP.get(name,0) >= wip_max:
        try:
            _mirror_background_event(
                f"[ACT_GUARD_WIP_LIMIT] {name}",
                "act_guard",
                "wip_limit",
            )
        except Exception:
            pass
        return {"ok": False, "error":"wip_limit"}

    # zapusk s taymerom
    res: Dict[str,Any] = {"ok": False, "error":"not_started"}
    def target():
        nonlocal res
        try:
            if callable(func):
                out=func(args)
                res = out if isinstance(out, dict) else {"ok": True, "result": out}
            else:
                res={"ok": False, "error":"func_not_registered"}
        except Exception as e:
            res={"ok": False, "error": str(e)}

    t=threading.Thread(target=target, daemon=True)
    _inc(name); t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        # taymaut
        with _LOCK:
            _REG.setdefault(name, {"stats":{"ok":0,"fail":0,"timeout":0}})["stats"]["timeout"]= _REG[name]["stats"].get("timeout",0)+1
        _dec(name)
        _passport("act_timeout", {"name": name, "timeout": timeout})
        try:
            _mirror_background_event(
                f"[ACT_GUARD_TIMEOUT] {name}",
                "act_guard",
                "timeout",
            )
        except Exception:
            pass
        return {"ok": False, "error":"timeout"}
    _dec(name)
    with _LOCK:
        if res.get("ok"): _REG.setdefault(name, {"stats":{"ok":0,"fail":0,"timeout":0}})["stats"]["ok"]= _REG[name]["stats"].get("ok",0)+1
        else:            _REG.setdefault(name, {"stats":{"ok":0,"fail":0,"timeout":0}})["stats"]["fail"]= _REG[name]["stats"].get("fail",0)+1
    _passport("act_run", {"name": name, "ok": res.get("ok",False)})
    try:
        _mirror_background_event(
            f"[ACT_GUARD_RUN] {name} ok={int(bool(res.get('ok')))}",
            "act_guard",
            "run",
        )
    except Exception:
        pass
    return res

# pri importe — popytka podtsepitsya k iskhodnomu action_registry
hook_register()
# c=a+b
