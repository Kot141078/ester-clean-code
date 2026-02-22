# -*- coding: utf-8 -*-
"""
modules/coop/net_playback.py — setevoy pleybek: veduschiy sinkhronno shagaet stsenariy, vedomye povtoryayut.

Ideya:
- Veduschiy: lokalno vyzyvaet interaktivnyy pleybek (modules/coop/interactive_playback.py) i parallelno
  rassylaet komandam peers tekuschiy shag (action/check), a takzhe komandy upravleniya (start/pause/resume/stop/seek).
- Vedomye: prinimayut komandy cherez /netplay/ingest i vypolnyayut ikh lokalno (bez sobstvennoy logiki stsenariya).

Format setevoy komandy:
  {"cmd":"step","step":{"action":{...},"check":{...},"timeout_ms":3000},"index":N}
  {"cmd":"control","op":"start|pause|resume|stop|next|prev","index":N?}

MOSTY:
- Yavnyy: (Orkestratsiya ↔ Set) odin stsenariy — mnogo ekranov.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) yavnye komandy i podtverzhdeniya.
- Skrytyy #2: (Kibernetika ↔ Volya) liderskoe reshenie — u vsekh odno sostoyanie.

ZEMNOY ABZATs:
Obychnye HTTP POST na lokalnyy /peer/proxy s probrosom na peers. Nikakikh brokerov/soketov.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"peers": [], "leader": True}

def set_peers(arr: List[str]) -> Dict[str, Any]:
    _state["peers"] = list(arr or [])
    return {"ok": True, "peers": _state["peers"]}

def status() -> Dict[str, Any]:
    return {"ok": True, **_state}

def _post_local(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type": "application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _broadcast(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for host in _state.get("peers", []):
        try:
            out.append(_post_local("/peer/proxy", {"host": host, "path": "/netplay/ingest", "payload": payload}))
        except Exception as e:
            out.append({"ok": False, "error": str(e)})
    return out

def leader_step(step: Dict[str, Any], index: int) -> Dict[str, Any]:
    # lokalno proigryvaem odin shag cherez interaktiv
    _post_local("/iplay/load", {"steps": [step]})
    _post_local("/iplay/start", {})
    # shirokoveschatelno
    res = _broadcast({"cmd": "step", "step": step, "index": int(index)})
    return {"ok": True, "peers": res}

def leader_control(op: str, index: int | None = None) -> Dict[str, Any]:
    res = _broadcast({"cmd": "control", "op": op, "index": index})
    return {"ok": True, "peers": res}

def follower_ingest(pkt: Dict[str, Any]) -> Dict[str, Any]:
    cmd = (pkt.get("cmd") or "").lower()
    if cmd == "step":
        st = pkt.get("step") or {}
        # vypolnit deystvie i proverku kak v interaktivnom pleybeke (minimalno)
        act = st.get("action") or {}
        chk = st.get("check") or {}
        to  = int(st.get("timeout_ms", 3000))
        _post_local("/attention/journal/append", {"event": "netplay_recv", "detail": {"cmd":"step","index":pkt.get("index",0)}})
        # deystvie
        if act.get("type") == "hotkey":
            _post_local("/desktop/window/hotkey", {"seq": act.get("seq","")})
        elif act.get("type") == "mix_apply":
            _post_local("/profiles/mix/apply", {"title": act.get("title","")})
        elif act.get("type") == "workflow":
            _post_local("/rpa/workflows/run", {"name": act.get("name","")})
        # prostaya proverka (OCR/shablon), bez lupov dlya kratkosti
        if chk:
            scr = _post_local("/desktop/rpa/screen", {})
            png = (scr.get("png_b64") or "") if scr.get("ok") else ""
            if (chk.get("kind") or "") == "ocr_contains":
                _post_local("/desktop/rpa/ocr_contains", {"png_b64": png, "needle": chk.get("text",""), "lang": chk.get("lang","eng+rus")})
            elif (chk.get("kind") or "") == "template_match":
                _post_local("/desktop/vision/template/find", {"screen_b64": png, "template_b64": chk.get("template_b64",""), "threshold": float(chk.get("threshold",0.78))})
        return {"ok": True}
    if cmd == "control":
        op = (pkt.get("op") or "").lower()
        # dlya sovmestimosti prosto logiruem (detalnaya sinkhronizatsiya statusa ne trebuetsya)
        _post_local("/attention/journal/append", {"event": "netplay_ctrl", "detail": {"op": op, "index": pkt.get("index")}})
        return {"ok": True}
    return {"ok": False, "error": "bad_cmd"}