# -*- coding: utf-8 -*-
"""
modules/computer_use/engine.py — A/B-dvizhok «Computer Use».

Soderzhit: profili taymautov, hooks, input human-typing, captcha-politiku, sandbox,
human-mouse (hover/scroll), profil klikov, stabilizator lokatorov, Stabilizer++ (networkidle/animations),
mini-replay, rate/throttle, anchors/fieldmap/valmask/bind i t.d.

MOSTY:
- Yavnyy: (Stabilizer++ ↔ Ispolnenie) — posle deystviy zhdem network-idle i okonchanie animatsiy.
- Skrytyy №1: (Nablyudaemost ↔ Nadezhnost) — v extra shaga logiruyutsya ozhidaniya stabilizatsii.
- Skrytyy №2: (Upravlenie ↔ Prozrachnost) — vklyuchenie cherez ENV ili per-step `after_wait`.

ZEMNOY ABZATs:
Eto «plavnyy tormoz»: snizhaem flap testov na dinamicheskikh saytakh — ne rvemsya dalshe, poka stranitsa ne uspokoilas.

c=a+b
"""
from __future__ import annotations
import importlib, os, hashlib, json, time, re, random
from html.parser import HTMLParser
from typing import Any, Dict, List
from urllib.request import Request, urlopen
from urllib.error import URLError

from .policy import check_url_allowed, allow_rate, base_dir
from .store import append_step, set_status, load_job
from .privacy import redact_dom, should_capture_screenshot
from modules.judge.hints import analyze_step
from modules.judge.verifier import evaluate_step
from modules.judge.policy import consider_step

from .descriptors import build_label_map, xpath_contains_text, find_manual_selector
from .macro import expand as macro_expand
from .wizard import plan as wizard_plan
from .learning import observe as learning_observe
from .conditions import eval_on_dom, eval_on_page
from .extract import extract_many as _extract_many
from .kvstore import set_many as kv_set_many

from . import events as _events
from . import profiles as _profiles
from . import downloader as _dl
from . import uploader as _uploader
from . import anchors as _anchors
from . import timeout_policy as _tpol
from . import valias as _valias
from . import valmask as _valmask
from . import jsonutil as _jsonutil
from . import fieldmap as _fieldmap
from . import databind as _bind
from . import ratelimit as _rl
from . import stepguard as _sg
from . import hooks as _hooks
from . import timeout_profiles as _tprof
from . import input_profiles as _iprofiles
from . import captcha as _captcha
from . import mouse_profiles as _mprofiles
from . import click_profiles as _cprofiles
from . import stabilizer_plus as _splus  # NEW
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _ENV(name: str, default: str) -> str:
    try: return os.getenv(name, default)
    except Exception: return default

MAX_STEPS = int(_ENV("COMPUTER_USE_MAX_STEPS", "20") or "20")
DEF_RETRY  = int(_ENV("COMPUTER_USE_RETRY", "2") or "2")
LOOP_GUARD = int(_ENV("COMPUTER_USE_LOOP_GUARD", "5") or "5")
IF_SLOT    = (_ENV("COMPUTER_USE_IF_SLOT","A") or "A").upper()
CHAIN_SLOT = (_ENV("COMPUTER_USE_CHAIN_SLOT","A") or "A").upper()
TO_SLOT    = (_ENV("COMPUTER_USE_TIMEOUT_SLOT","A") or "A").upper()
SHOT_ERR   = (str(_ENV("COMPUTER_USE_SHOT_ON_ERROR","1")).strip() != "0")
BIND_SLOT  = (_ENV("COMPUTER_USE_BIND_SLOT","A") or "A").upper()
HOOKS_ON   = (_ENV("COMPUTER_USE_HOOKS_SLOT","A") or "A").upper() == "B"
SANDBOX_ON = (_ENV("COMPUTER_USE_SANDBOX_SLOT","A") or "A").upper() == "B"
MOUSE_ON   = (_ENV("COMPUTER_USE_MOUSE_SLOT","A") or "A").upper() == "B"
CLICK_ON   = (_ENV("COMPUTER_USE_CLICK_SLOT","A") or "A").upper() == "B"
STAB_ON    = (_ENV("COMPUTER_USE_STABILIZER_SLOT","A") or "A").upper() == "B"
STAB_PLUS  = (_ENV("COMPUTER_USE_STABILIZER_PLUS_SLOT","A") or "A").upper() == "B"  # NEW

def _emit(kind: str, payload: Dict[str, Any]) -> None:
    try: _events.add(kind, payload)
    except Exception: pass

def _limits_from_env_or_prof(url: str) -> Dict[str, Any]:
    lim = {"backoff": float(_ENV("COMPUTER_USE_WAIT_BACKOFF","1.8") or "1.8"),
           "max_ms": int(_ENV("COMPUTER_USE_WAIT_MAX_MS","8000") or "8000"),
           "default_wait_ms": int(_ENV("COMPUTER_USE_DEFAULT_WAIT_MS","250") or "250")}
    if TO_SLOT == "B":
        lim.update({"backoff": 2.5, "max_ms": 15000, "default_wait_ms": 350})
    prof = _tpol.backoff_limits(url)
    if isinstance(prof, dict):
        if "mult" in prof: lim["backoff"] = float(prof["mult"])
        if "max_ms" in prof: lim["max_ms"] = int(prof["max_ms"])
        if "default_wait_ms" in prof: lim["default_wait_ms"] = int(prof["default_wait_ms"])
    tprof = _tprof.get_for_url(url)
    if isinstance(tprof, dict):
        if "mult" in tprof: lim["backoff"] = float(tprof["mult"])
        if "max_ms" in tprof: lim["max_ms"] = int(tprof["max_ms"])
        if "default_wait_ms" in tprof: lim["default_wait_ms"] = int(tprof["default_wait_ms"])
    return lim

class _ElemParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elems: List[Dict[str, str]] = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("a","button","input","select","textarea") or a.get("role") in ("button","link"):
            txt = a.get("aria-label") or a.get("value") or a.get("alt") or a.get("title") or ""
            href = a.get("href") or ""
            self.elems.append({"tag": tag, "href": href, "label": txt})

def _segmentation(dom: str) -> List[Dict[str, str]]:
    p = _ElemParser(); 
    try: p.feed(dom[:500000])
    except Exception: pass
    return p.elems[:200]

def _hash_dom(dom: str) -> str:
    return hashlib.sha1((dom or "")[:1000000].encode("utf-8")).hexdigest()

def _save_bytes(path: str, data: bytes) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f: f.write(data)
    return path

def _playwright_available() -> bool:
    try: return importlib.util.find_spec("playwright") is not None
    except Exception: return False

def _maybe_expand_actions(actions: List[Dict]) -> List[Dict]:
    out: List[Dict] = []
    for a in (actions or []):
        for x in macro_expand(a): out.append(x)
    return out

def _append_and_policy(job_id: str, idx: int, mode: str, before_dom: str, after_dom: str, shot_path: str,
                       act: Dict[str, Any], attempts: int, ok: bool, used: str, manual_used: bool,
                       detail: str, extra_kv: Dict[str, Any] | None = None, domain: str = "") -> Dict[str, Any]:
    h = analyze_step(before_dom, after_dom, act)
    v = evaluate_step(h, act)
    ex = {"mode": mode, "action": act, "attempts": attempts, "ok": ok,
          "used": used, "manual_used": manual_used, "detail": detail,
          "hash_before": _hash_dom(before_dom), "hash_after": _hash_dom(after_dom), 
          "hints": h, "verify": v}
    if extra_kv: ex.update(extra_kv)
    append_step(job_id, f"action:{act.get('type','unknown')}", 
                before_dom=before_dom, after_dom=after_dom, screenshot_path=shot_path, extra=ex)
    learning_observe("", act, v, used=used, detail=detail)
    consider_step(job_id, idx, v, act, {})
    payload = {"job_id": job_id, "idx": idx, "kind": act.get("type","unknown"),
               "verdict": v.get("verdict","off"), "domain": domain}
    if extra_kv and ("dur_ms" in extra_kv): payload["dur_ms"] = extra_kv["dur_ms"]
    _emit("step", payload)
    return {"hints": h, "verify": v}

def _out_dir(job_id: str) -> str:
    return os.path.join(base_dir(), "artifacts", job_id)

def _prepend_chain(actions: List[Dict], url: str) -> List[Dict]:
    try:
        from urllib.parse import urlparse
        dom = (urlparse(url).hostname or "").lower()
        chain = _profiles.get_chain(dom)
        if not chain: return actions
        if CHAIN_SLOT == "B":
            return chain + actions if not actions or actions[0].get("type") not in ("open","navigate") else actions
        return chain + actions
    except Exception:
        return actions

def _resolve_anchor(url: str, act: Dict[str, Any]) -> Dict[str, Any]:
    a = dict(act or {})
    anch = (a.get("pre_anchor") or a.get("anchor") or "").strip()
    sel = (a.get("selector") or "").strip()
    if anch:
        r = _anchors.resolve(url, anch)
        if r: a["selector"] = r; a["_anchor_used"] = anch
        return a
    if sel.startswith("@"):
        nm = sel[1:]; r = _anchors.resolve(url, nm)
        if r: a["selector"] = r; a["_anchor_used"] = nm
    return a

def _resolve_field(url: str, act: Dict[str, Any]) -> Dict[str, Any]:
    a = dict(act or {})
    if (a.get("type") or "").strip() not in ("input","fill_form"):
        return a
    if a.get("type") == "input" and not a.get("selector"):
        fld = (a.get("field") or "").strip().lower()
        if fld:
            sel = _fieldmap.resolve(url, fld)
            if sel: a["selector"] = sel; a["_field_used"] = fld
    return a

def _apply_valias(url: str, act: Dict[str, Any]) -> Dict[str, Any]:
    return _valias.apply_to_action(url, act)

def _apply_valmask(url: str, act: Dict[str, Any]) -> Dict[str, Any]:
    a = dict(act or {})
    if (a.get("type") or "").strip() != "input":
        return a
    val = str(a.get("value") or "")
    mask = (a.get("mask") or "").strip()
    mask_re = (a.get("mask_re") or "").strip() or None
    on_fail = (a.get("on_fail") or "warn").lower()
    if not (mask or mask_re):
        return a
    ok, value_norm, mask_name = _valmask.validate(url, val, mask or "", explicit_regex=mask_re)
    a["_mask_name"] = mask_name
    a["_mask_ok"] = bool(ok)
    if ok or on_fail == "strip": a["value"] = value_norm
    if (not ok) and on_fail == "error": a["_mask_error"] = True
    return a

def _bind_actions(url: str, actions: List[Dict], meta: Dict[str, Any]) -> List[Dict]:
    vars_meta = (meta or {}).get("vars") or {}
    actions_vars = {}
    if BIND_SLOT == "B" and isinstance(actions, list) and actions and isinstance(actions[0], dict):
        if isinstance(actions[0].get("vars"), dict):
            actions_vars = actions[0]["vars"]
    return _bind.bind_actions(url, actions, vars_meta, actions_vars)

def _guard_gate(domain: str, key: str) -> int:
    ok, tok, why, wait_ms = _sg.acquire(domain, key)
    if not ok:
        time.sleep(0.4)
        return 400
    if wait_ms>0:
        try: time.sleep(wait_ms/1000.0)
        except Exception: pass
    try: _sg.release(domain, key, tok)
    except Exception: pass
    return int(wait_ms)