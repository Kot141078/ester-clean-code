# -*- coding: utf-8 -*-
"""
modules/thinking/actions_garage_sisters_ab.py — eksheny «voli» dlya Garazha/Sester/A-B.

Mosty:
- Yavnyy: (Mysli ↔ Masterskaya/Set/Bezopasnost) edinye knopki dlya postroeniya i raspredeleniya.
- Skrytyy #1: (Profile ↔ Prozrachnost) fiksiruem upravlyayuschie deystviya.
- Skrytyy #2: (Rules/Cron ↔ Avtonomiya) mozhno zapuskat iz raspisaniya/sobytiy.

Zemnoy abzats:
S etimi komandami Ester sama sozdaet moduli, gonyaet sborku, podklyuchaet i rassylaet zadachi po seti.

# c=a+b
"""
from __future__ import annotations
import json, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def _get(path: str, timeout: int=30):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    def _post(path: str, payload: dict, timeout: int=120):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    # Garage
    register("garage.projects", {}, {"ok":"bool"}, 1, lambda a: _get("/garage/projects"))
    register("garage.project.create", {"name":"str","route_base":"str","owner":"str"}, {"ok":"bool"}, 2, lambda a: _post("/garage/project/create", {"name": a.get("name",""), "route_base": a.get("route_base","/garage"), "owner": a.get("owner","")}))
    register("garage.project.add_file", {"name":"str","rel_path":"str","content":"str"}, {"ok":"bool"}, 2, lambda a: _post("/garage/project/add_file", {"name": a.get("name",""), "rel_path": a.get("rel_path",""), "content": a.get("content","")}))
    register("garage.project.build", {"name":"str"}, {"ok":"bool"}, 1, lambda a: _post("/garage/project/build", {"name": a.get("name","")}))
    register("garage.project.register", {"name":"str"}, {"ok":"bool"}, 1, lambda a: _post("/garage/project/register", {"name": a.get("name","")}))

    # Sisters
    register("sisters.list", {}, {"ok":"bool"}, 1, lambda a: _get("/sisters/list"))
    register("sisters.upsert", {"name":"str","base_url":"str","caps":"list"}, {"ok":"bool"}, 1, lambda a: _post("/sisters/upsert", {"name": a.get("name",""), "base_url": a.get("base_url",""), "caps": list(a.get("caps") or [])}))
    register("sisters.assign", {"name":"str","path":"str","payload":"object"}, {"ok":"bool"}, 1, lambda a: _post("/sisters/assign", {"name": a.get("name",""), "path": a.get("path",""), "payload": dict(a.get("payload") or {})}))

    # AB
    register("safety.ab.status", {}, {"ok":"bool"}, 1, lambda a: _get("/safety/ab/status"))
    register("safety.ab.switch", {"slot":"str"}, {"ok":"bool"}, 1, lambda a: _post("/safety/ab/switch", {"slot": a.get("slot","A")}))
_reg()
# c=a+b