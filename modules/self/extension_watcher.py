# -*- coding: utf-8 -*-
"""
modules/self/extension_watcher.py — nablyudatel za rasshireniyami:
skaniruet incoming → proveryaet → safe → drafts/enabled, risky → quarantine, vedet zhurnal, podderzhivaet «tabletku».

Mosty:
- Yavnyy: (Inzheneriya ↔ Volya) Ester sama nakhodit novye moduli i prinimaet reshenie, ostavayas pod predokhranitelyami.
- Skrytyy #1: (Bezopasnost ↔ Audit) karantin + append-only zhurnal + podpisi (opts.) → mozhno dokazat, chto ne «podsunuli».
- Skrytyy #2: (Kibernetika ↔ Kontrol) «tabletka» — korotkiy operatorskiy overrayd dlya pogranichnykh sluchaev.

Zemnoy abzats:
Eto kak «priemka na sklad»: vse novoe prokhodit proverku, somnitelnoe — v karantin, bezopasnoe — v rabotu, vse pod zapis.

# c=a+b
"""
from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.getenv("SELF_CODE_ROOT", "extensions")
INCOMING = os.path.join(ROOT, "incoming")
QUAR = os.path.join(ROOT, "quarantine")
DRAFTS = os.path.join(ROOT, "drafts")
ENABLED = os.path.join(ROOT, "enabled")
CHAIN = "data/self/ext_watch_chain.jsonl"
TRUST_DIR = os.getenv("TRUST_PUBKEYS_DIR", "data/trust/pubkeys")

AB = (os.getenv("EXT_WATCH_AB", "A") or "A").upper()
REQ_SIG = bool(int(os.getenv("EXT_WATCH_REQUIRE_SIGNATURE", "0")))
AUTO_APPLY_SAFE = bool(int(os.getenv("EXT_WATCH_AUTO_APPLY_SAFE", "0")))
ALLOW_APPLY = bool(int(os.getenv("SELF_CODE_ALLOW_APPLY", "0")))
DENY = {x.strip() for x in (os.getenv("SELF_CODE_DENY_IMPORTS","") or "").split(",") if x.strip()}

# --- utility ---

def _ensure_dirs():
    for p in (INCOMING, QUAR, DRAFTS, ENABLED, os.path.dirname(CHAIN), TRUST_DIR):
        os.makedirs(p, exist_ok=True)

def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _append_chain(event: Dict[str, Any]) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(CHAIN), exist_ok=True)
    prev = ""
    try:
        with open(CHAIN, "rb") as f:
            f.seek(0, os.SEEK_END)
            if f.tell() > 0:
                size = min(4096, f.tell())
                f.seek(-size, os.SEEK_END)
                tail = f.read().decode("utf-8", "ignore")
                lines = [ln for ln in tail.strip().splitlines() if ln.strip()]
                for ln in reversed(lines):
                    try:
                        j = json.loads(ln)
                        prev = j.get("own_hash","")
                        break
                    except Exception:
                        continue
    except Exception:
        pass
    e = {"ts": int(time.time()), **event, "prev_hash": prev}
    own = hashlib.sha256(json.dumps(e, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    e["own_hash"] = own
    with open(CHAIN, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return e

# --- «tabletka»: odnorazovyy/vremennyy overrayd politik ---

PILL_FILE = "data/self/ext_watch_pill.json"

def _pill_state() -> Dict[str, Any]:
    try:
        j = json.load(open(PILL_FILE, "r", encoding="utf-8"))
    except Exception:
        j = {"armed": False, "until": 0}
    if j.get("armed") and int(time.time()) > int(j.get("until", 0)):
        j = {"armed": False, "until": 0}
    return j

def pill_arm(ttl_sec: int = 300) -> Dict[str, Any]:
    st = {"armed": True, "until": int(time.time()) + max(30, int(ttl_sec))}
    os.makedirs(os.path.dirname(PILL_FILE), exist_ok=True)
    json.dump(st, open(PILL_FILE, "w", encoding="utf-8"))
    _append_chain({"event":"pill_arm","ttl":ttl_sec})
    return {"ok": True, **_pill_state()}

def pill_disarm() -> Dict[str, Any]:
    st = {"armed": False, "until": 0}
    os.makedirs(os.path.dirname(PILL_FILE), exist_ok=True)
    json.dump(st, open(PILL_FILE, "w", encoding="utf-8"))
    _append_chain({"event":"pill_disarm"})
    return {"ok": True, **_pill_state()}

# --- Proverki moduley ---

DANG_CALLS = {
    ("os","system"),
    ("subprocess","Popen"),
    ("subprocess","run"),
    (None,"eval"),
    (None,"exec"),
    (None,"__import__"),
}

def _deny_imports_check(tree: ast.AST) -> List[str]:
    bad = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in (n.names or []):
                if a.name in DENY:
                    bad.append(a.name)
    return bad

def _danger_calls_check(tree: ast.AST) -> List[str]:
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name):
                mod = n.func.value.id
                name = n.func.attr
                if (mod, name) in DANG_CALLS:
                    hits.append(f"{mod}.{name}")
            elif isinstance(n.func, ast.Name):
                nm = n.func.id
                if (None, nm) in DANG_CALLS:
                    hits.append(nm)
    return hits

def _signature_ok(path_py: str, content: str) -> Optional[bool]:
    """Proverka Ed25519 podpisi dlya sha256(content).
    Ischem .sig ryadom: <file.py>.sig (base64). Berem lyuboy publichnyy klyuch iz TRUST_PUBKEYS_DIR."""
    sig_path = path_py + ".sig"
    if not os.path.isfile(sig_path):
        return None  # net podpisi
    try:
        import nacl.signing  # type: ignore
        import nacl.exceptions  # type: ignore
    except Exception:
        return None  # net PyNaCl — ne mozhem verifitsirovat
    sig_b64 = open(sig_path, "r", encoding="utf-8").read().strip()
    try:
        sig = base64.b64decode(sig_b64)
    except Exception:
        return False
    digest = bytes.fromhex(_sha256_text(content))
    ok_any = False
    if not os.path.isdir(TRUST_DIR):
        return False
    for fn in os.listdir(TRUST_DIR):
        if not fn.endswith(".txt"): 
            continue
        try:
            pk_b64 = open(os.path.join(TRUST_DIR, fn), "r", encoding="utf-8").read().strip()
            pk = base64.b64decode(pk_b64)
            vk = nacl.signing.VerifyKey(pk)
            try:
                vk.verify(digest, sig)
                ok_any = True
                break
            except nacl.exceptions.BadSignatureError:
                continue
        except Exception:
            continue
    return ok_any

def analyze_content(name: str, content: str) -> Dict[str, Any]:
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return {"ok": False, "reason": f"syntax:{e}"}
    denies = _deny_imports_check(tree)
    dangers = _danger_calls_check(tree)
    sig_ok = None  # None=net, True/False=rezultat proverki
    # signatura proveryaetsya pozzhe, kogda uznaem put
    score = 0
    if denies: score += 2
    if dangers: score += 2
    return {"ok": True, "denies": denies, "dangers": dangers, "sig_ok": sig_ok, "score": score}

def _write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content if content.endswith("\n") else content + "\n")

# --- Dvizhok skanirovaniya ---

def _list_py(dirpath: str) -> List[str]:
    try:
        return sorted([f for f in os.listdir(dirpath) if f.endswith(".py")])
    except Exception:
        return []

def scan(auto: bool = False) -> Dict[str, Any]:
    """
    Skaniruet incoming → prinimaet resheniya.
    Vozvraschaet: {"ok":True,"checked":[...],"applied":[...],"quarantined":[...],"drafted":[...]}
    """
    _ensure_dirs()
    if AB == "B":
        return {"ok": False, "error": "EXT_WATCH_AB=B"}
    checked, applied, quarantined, drafted = [], [], [], []

    for fn in _list_py(INCOMING):
        p = os.path.join(INCOMING, fn)
        try:
            content = open(p, "r", encoding="utf-8").read()
        except Exception as e:
            checked.append({"name": fn, "error": f"read:{e}"})
            continue

        rep = analyze_content(fn, content)
        # dopolnit signaturu (esli fayl .sig est)
        sig = _signature_ok(p, content)
        rep["sig_ok"] = sig

        decision = "quarantine"
        reason = []
        if not rep.get("ok"):
            reason.append(rep.get("reason","parse-fail"))
        else:
            if REQ_SIG and sig is not True:
                reason.append("signature-required")
            if rep.get("denies"): 
                reason.append("deny-imports")
            if rep.get("dangers"):
                reason.append("danger-calls")

            pill = _pill_state()
            pill_ok = bool(pill.get("armed"))
            if not reason:
                decision = "safe"
            elif pill_ok:
                decision = "safe-pill"
                reason.append("pill")

        # primenyaem reshenie
        if decision.startswith("safe"):
            # zapishem v drafts i, esli razresheno, proverim/vklyuchim
            draft_path = os.path.join(DRAFTS, fn)
            _write(draft_path, content)
            drafted.append(fn)

            # progon cherez pesochnitsu
            try:
                from modules.self.code_sandbox import check as _check, apply as _apply  # type: ignore
                chk = _check(fn.replace(".py",""))
                if not chk.get("ok"):
                    reason.append(f"check:{chk.get('error')}")
                    decision = "quarantine"
                else:
                    if ALLOW_APPLY and (AUTO_APPLY_SAFE or (auto and decision=="safe")):
                        ap = _apply(fn.replace(".py",""))
                        if ap.get("ok"):
                            applied.append(fn)
                            _append_chain({"event":"apply", "name": fn, "mode":"auto" if auto else "manual"})
                        else:
                            reason.append(f"apply:{ap.get('error')}")
                            decision = "quarantine"
            except Exception as e:
                reason.append(f"sandbox:{e}")
                decision = "quarantine"

        if decision == "quarantine":
            qpath = os.path.join(QUAR, fn)
            _write(qpath, content)
            quarantined.append({"name": fn, "reason": reason})

        # zhurnal
        _append_chain({"event":"scan_decision","name":fn,"decision":decision,"reason":reason,"sig":sig})

        # udalyaem iz incoming
        try:
            os.remove(p)
        except Exception:
            pass

        checked.append({"name": fn, "decision": decision, "reason": reason, "sig": sig})

    return {"ok": True, "checked": checked, "applied": applied, "quarantined": quarantined, "drafted": drafted}

# --- Operatsii s karantinom ---

def approve(name: str) -> Dict[str, Any]:
    _ensure_dirs()
    src = os.path.join(QUAR, name)
    if not os.path.isfile(src):
        return {"ok": False, "error": "not in quarantine"}
    content = open(src, "r", encoding="utf-8").read()
    # uvazhim politiku: esli REQ_SIG=1 i net podpisi — trebuem «tabletku»
    must_pill = REQ_SIG and (_signature_ok(src, content) is not True)
    if must_pill and not _pill_state().get("armed"):
        return {"ok": False, "error": "signature-required; pill not armed"}
    # v drafts
    draft_path = os.path.join(DRAFTS, name)
    _write(draft_path, content)
    # pesochnitsa -> apply (esli razresheno)
    from modules.self.code_sandbox import check as _check, apply as _apply  # type: ignore
    chk = _check(name.replace(".py",""))
    if not chk.get("ok"):
        return {"ok": False, "error": f"check:{chk.get('error')}"}
    res: Dict[str, Any] = {"ok": True, "drafted": True}
    if ALLOW_APPLY:
        ap = _apply(name.replace(".py",""))
        res["applied"] = bool(ap.get("ok"))
        if not ap.get("ok"):
            res["apply_error"] = ap.get("error")
        else:
            _append_chain({"event":"apply","name":name,"mode":"approve"})
    # uberem iz karantina
    try:
        os.remove(src)
    except Exception:
        pass
    return res

def reject(name: str) -> Dict[str, Any]:
    _ensure_dirs()
    src = os.path.join(QUAR, name)
    if not os.path.isfile(src):
        return {"ok": False, "error": "not in quarantine"}
    os.remove(src)
    _append_chain({"event":"reject","name":name})
    return {"ok": True}

# --- Status/tsepochka ---

def status() -> Dict[str, Any]:
    _ensure_dirs()
    pill = _pill_state()
    return {
        "ok": True,
        "ab": AB,
        "policy": {
            "require_signature": REQ_SIG,
            "auto_apply_safe": AUTO_APPLY_SAFE,
            "allow_apply": ALLOW_APPLY,
            "deny_imports": sorted(list(DENY)),
        },
        "counts": {
            "incoming": len(_list_py(INCOMING)),
            "quarantine": len(_list_py(QUAR)),
            "drafts": len(_list_py(DRAFTS)),
            "enabled": len(_list_py(ENABLED)),
        },
        "pill": pill,
    }

def chain_tail(limit: int = 1000) -> Dict[str, Any]:
    try:
        lines = [ln for ln in open(CHAIN, "r", encoding="utf-8").read().splitlines() if ln.strip()]
    except Exception:
        lines = []
    if limit > 0 and len(lines) > limit:
        lines = lines[-limit:]
    out: List[Dict[str, Any]] = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return {"ok": True, "tail": out}