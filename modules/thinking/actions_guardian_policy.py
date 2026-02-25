# -*- coding: utf-8 -*-
"""modules/thinking/actions_guardian_policy.py - eksheny "voli" dlya SelfCatalog/Guardian/LegalGuard.

Mosty:
- Yavnyy: (Mysli ↔ Servisy Zaboty/Politik) pozvolyaet Ester deystvovat osoznanno i ostorozhno.
- Skrytyy #1: (Plan ↔ Prozrachnost) bystraya samoopis pered resheniyami.
- Skrytyy #2: (Profile ↔ Audit) pochti vse operatsii logiruyutsya v drugikh modulyakh.

Zemnoy abzats:
Nabor korotkikh komand: “who ya seychas”, “where is my kontakty”, “mozhno li eto?”, “kak eskalirovat, esli nuzhno”.

# c=a+b"""
from __future__ import annotations
import json, urllib.request
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def _get(path: str, timeout: int=20):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    def _post(path: str, payload: Dict[str,Any], timeout: int=30):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("self.catalog", {}, {"ok":"bool"}, 1, lambda a: _get("/self/catalog"))
    register("self.capabilities", {}, {"ok":"bool"}, 1, lambda a: _get("/self/capabilities"))

    register("guardian.contact.upsert", {"id":"str","name":"str"}, {"ok":"bool"}, 2, lambda a: _post("/guardian/contact/upsert", dict(a or {})))
    register("guardian.contact.list", {}, {"ok":"bool"}, 1, lambda a: _get("/guardian/contact/list"))
    register("guardian.escalate.prepare", {"kind":"str","who":"str","message":"str"}, {"ok":"bool"}, 2,
             lambda a: _post("/guardian/escalate/prepare", {"kind": a.get("kind","emergency"), "who": a.get("who",""), "message": a.get("message","")}))

    register("policy.legal.check", {"task":"object"}, {"ok":"bool"}, 1, lambda a: _post("/policy/legal/check", {"task": dict(a.get("task") or {})}))

_reg()
# c=a+b