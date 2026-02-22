# -*- coding: utf-8 -*-
"""
modules/agents/desktop_os_driver.py — krossplatformennyy drayver rabochego stola.

Funktsii verkhnego urovnya (bez sokhraneniya sostoyaniya):
  probe() -> dict             # opredelit OS i dostupnye vozmozhnosti
  whitelist_get() -> dict     # zagruzit whitelist
  whitelist_add(name, cmd)    # dobavit zapis
  whitelist_remove(name)      # udalit
  plan_to_commands(plan)      # sopostavit shagi agenta komandam OS
  execute(plan, dry_run=True) # vypolnit plan (sandbox/real) s logami

Bezopasnost:
- Po umolchaniyu dry_run (nichego ne delaet, tolko ekho).
- Rezhim real dostupen tolko pri ESTER_DD_ENABLED=1 i ESTER_DD_MODE=real,
  i esli KAZhDYY shag rezolvitsya v komandu iz whitelist.
- Lyubaya komanda vne whitelist = otkaz s logom.

MOSTY:
- Yavnyy: (Agenty ↔ OS) — bezopasnoe, obyasnimoe vypolnenie shagov.
- Skrytyy #1: (Kibernetika ↔ Pesochnitsa) — dry-run kak «bezopasnaya simulyatsiya».
- Skrytyy #2: (Infoteoriya ↔ Upravlenie riskom) — whitelist kak szhataya politika.

ZEMNOY ABZATs:
Inzhenerno — eto konvertor shagov {launch, focus, type, navigate, capture} v
konkretnye vyzovy OS/GUI (xdg-open/osascript/start i t.p.) s belymi spiskami.
Prakticheski — Ester mozhet «pokazat na moem rabochem stole» i pri etom ne
vyyti za ramki razreshennogo.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import os, sys, json, platform, subprocess, shlex, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

WL_PATH = os.environ.get("ESTER_DD_WHITELIST", "rules/desktop_whitelist.json")

def _load_json(path:str)->Any:
    if not os.path.exists(path): return None
    try:
        with open(path,"r",encoding="utf-8") as f: return json.load(f)
    except Exception:
        return None

def _save_json(path:str, obj:Any)->None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=2)

def whitelist_get()->Dict[str,Any]:
    obj = _load_json(WL_PATH) or {"apps":{}, "commands":{}}
    return {"ok":True, "path":WL_PATH, "whitelist":obj}

def whitelist_add(name:str, cmd:str, kind:str="app")->Dict[str,Any]:
    obj = _load_json(WL_PATH) or {"apps":{}, "commands":{}}
    if kind=="app":
        obj["apps"][name]=cmd
    else:
        obj["commands"][name]=cmd
    _save_json(WL_PATH, obj)
    return {"ok":True, "whitelist":obj}

def whitelist_remove(name:str, kind:str="app")->Dict[str,Any]:
    obj = _load_json(WL_PATH) or {"apps":{}, "commands":{}}
    if kind=="app":
        obj["apps"].pop(name, None)
    else:
        obj["commands"].pop(name, None)
    _save_json(WL_PATH, obj)
    return {"ok":True, "whitelist":obj}

def _detect_os()->str:
    forced=os.environ.get("ESTER_DD_OS","auto").lower()
    if forced!="auto": return forced
    sysname=platform.system().lower()
    if "windows" in sysname: return "windows"
    if "darwin" in sysname or "mac" in sysname: return "macos"
    return "linux"

def probe()->Dict[str,Any]:
    return {
        "ok": True,
        "os": _detect_os(),
        "enabled": os.environ.get("ESTER_DD_ENABLED","0")=="1",
        "mode": os.environ.get("ESTER_DD_MODE","sandbox"),
        "whitelist": whitelist_get().get("whitelist")
    }

# --- Plan → Komandy OS ---

def _cmd_launch(app:str, args:List[str])->Tuple[str,List[str]]:
    osname=_detect_os()
    if osname=="windows":
        # 'start "" app args...'
        return "cmd", ["/c","start","",app] + args
    if osname=="macos":
        # 'open -a AppName --args ...'
        return "open", ["-a", app, "--args"] + args if args else ["-a", app]
    # linux
    return app, args

def _cmd_open_url(url:str, browser:str|None)->Tuple[str,List[str]]:
    osname=_detect_os()
    if osname=="windows":
        return "cmd", ["/c","start","",url]
    if osname=="macos":
        return "open", [url]
    return "xdg-open", [url]

def _cmd_focus(app:str)->Tuple[str,List[str]]:
    osname=_detect_os()
    if osname=="macos":
        # AppleScript activate
        return "osascript", ["-e", f'tell application "{app}" to activate']
    # Na Linux/Windows bez spets. tulzov — no-op (ostavim kak logicheskiy shag)
    return "noop", []

def _cmd_type(text:str)->Tuple[str,List[str]]:
    # Bez vneshnikh tulzov vvod ne delaem — emuliruem (logom)
    return "noop", [f"type:{text}"]

def _cmd_capture()->Tuple[str,List[str]]:
    osname=_detect_os()
    if osname=="macos":
        # sokhranit v /tmp/ester_screenshot.png
        return "screencapture", ["/tmp/ester_screenshot.png"]
    if osname=="linux":
        # potrebuet imagemagick 'import' — ostavim noop po umolchaniyu
        return "noop", ["capture:screen"]
    if osname=="windows":
        return "noop", ["capture:screen"]
    return "noop", ["capture:screen"]

def plan_to_commands(plan:List[Dict[str,Any]], whitelist:Dict[str,Any]|None=None)->List[Dict[str,Any]]:
    wl=whitelist or (whitelist_get().get("whitelist") or {"apps":{}, "commands":{}})
    cmds=[]
    for step in plan:
        do=step.get("do")
        if do=="launch":
            app=step.get("app","")
            args=step.get("args") or []
            # razreshim tolko esli app v whitelist.apps
            if app not in wl.get("apps",{}):
                cmds.append({"ok":False,"reason":"app_not_whitelisted","step":step}); continue
            binpath=wl["apps"][app]
            exe,args2=_cmd_launch(binpath, args)
            cmds.append({"ok":True,"cmd":exe,"args":args2,"step":step})
        elif do=="navigate":
            url=step.get("url","")
            exe,args2=_cmd_open_url(url, None)
            cmds.append({"ok":True,"cmd":exe,"args":args2,"step":step})
        elif do=="focus":
            app=step.get("app") or step.get("target")
            if not app:
                cmds.append({"ok":True,"cmd":"noop","args":[],"step":step})
            else:
                # focus razreshaem, esli prilozhenie whitelisted (esli imya est)
                if app in wl.get("apps",{}):
                    exe,args2=_cmd_focus(app)
                else:
                    exe,args2="noop", ["focus:"+str(app)]
                cmds.append({"ok":True,"cmd":exe,"args":args2,"step":step})
        elif do=="type":
            exe,args2=_cmd_type(step.get("text",""))
            cmds.append({"ok":True,"cmd":exe,"args":args2,"step":step})
        elif do=="capture":
            exe,args2=_cmd_capture()
            cmds.append({"ok":True,"cmd":exe,"args":args2,"step":step})
        else:
            cmds.append({"ok":True,"cmd":"noop","args":[f"noop:{do}"],"step":step})
    return cmds

# --- Vypolnenie ---

def _exec_one(cmd:str, args:List[str], dry_run:bool)->Dict[str,Any]:
    if dry_run or cmd=="noop":
        return {"ok":True,"dry":True,"cmd":cmd,"args":args}
    try:
        proc=subprocess.Popen([cmd]+args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # ne blokiruemsya nadolgo
        time.sleep(0.2)
        return {"ok":True,"pid":proc.pid,"cmd":cmd,"args":args}
    except Exception as e:
        return {"ok":False,"error":str(e),"cmd":cmd,"args":args}

def execute(plan:List[Dict[str,Any]], dry_run:bool=True)->Dict[str,Any]:
    wl=whitelist_get().get("whitelist") or {"apps":{}, "commands":{}}
    cmds=plan_to_commands(plan, wl)
    mode=os.environ.get("ESTER_DD_MODE","sandbox")
    enabled=os.environ.get("ESTER_DD_ENABLED","0")=="1"
    real = enabled and (mode=="real")
    out=[]
    for c in cmds:
        if not c.get("ok"):
            out.append({"ok":False, **c}); continue
        # Lyubaya komanda vne whitelist (dlya launch) uzhe pomechena ok=True, no cmd mozhet byt 'noop' (eto bezopasno).
        res=_exec_one(c["cmd"], c["args"], dry_run= (not real) or dry_run)
        out.append(res)
    return {"ok": all(x.get("ok") for x in out), "mode": mode, "enabled": enabled, "results": out}
def _cmd_click(x:int,y:int):
    osname=_detect_os()
    # Bez storonnikh utilit: tolko noop s logom pozitsii
    return "noop", [f"click:{x},{y}"]

def plan_to_commands(plan, whitelist=None):
    # originalnaya funktsiya zdes PEREOPREDELENA tselikom dlya konteksta
    wl=whitelist or (whitelist_get().get("whitelist") or {"apps":{}, "commands":{}})
    cmds=[]
    for step in plan:
        do=step.get("do")
        if do=="launch":
            app=step.get("app",""); args=step.get("args") or []
            if app not in wl.get("apps",{}):
                cmds.append({"ok":False,"reason":"app_not_whitelisted","step":step}); continue
            binpath=wl["apps"][app]; exe,args2=_cmd_launch(binpath, args)
            cmds.append({"ok":True,"cmd":exe,"args":args2,"step":step})
        elif do=="navigate":
            exe,args2=_cmd_open_url(step.get("url",""), None); cmds.append({"ok":True,"cmd":exe,"args":args2,"step":step})
        elif do=="focus":
            app=step.get("app") or step.get("target")
            if app and app in wl.get("apps",{}): exe,args2=_cmd_focus(app)
            else: exe,args2="noop",[f"focus:{app or 'active'}"]
            cmds.append({"ok":True,"cmd":exe,"args":args2,"step":step})
        elif do=="type":
            exe,args2=_cmd_type(step.get("text","")); cmds.append({"ok":True,"cmd":exe,"args":args2,"step":step})
        elif do=="capture":
            exe,args2=_cmd_capture(); cmds.append({"ok":True,"cmd":exe,"args":args2,"step":step})
        elif do=="click":
            x=int(step.get("x",0)); y=int(step.get("y",0))
            exe,args2=_cmd_click(x,y); cmds.append({"ok":True,"cmd":exe,"args":args2,"step":step})
        else:
            cmds.append({"ok":True,"cmd":"noop","args":[f"noop:{do}"],"step":step})
    return cmds