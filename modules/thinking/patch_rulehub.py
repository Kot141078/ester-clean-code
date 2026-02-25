# -*- coding: utf-8 -*-
"""modules/thinking/patch_rulehub.py - tonkaya “vrezka” v dvizhok pravil myshleniya bez smeny kontraktov.
Naznachenie: nablyudaemost, prioritizatsiya, kvoty na deystviya, zhurnal decision.

How it works:
- Pri importe, esli RULEHUB_ENABLED=1, oborachivaet modules.thinking_pipelines.run_rules (esli est).
- Logiruet kazhdoe srabatyvanie: input_len, actions, duration_ms, status, err.
- Primenyaet myagkie kvoty/prioritety iz config/rulehub.yaml (esli kvota=0 - ne ogranichivaem).
- Pishet sobytiya v data/rulehub/log.jsonl i schetchiki v data/rulehub/state.json.

Mosty:
- Yavnyy: (Kibernetika ↔ Logika) kvoty/prioritety stabiliziruyut povedenie v pikakh, sokhranyaya kachestvo decision.
- Skrytyy #1: (Infoteoriya ↔ Nablyudaemost) zhurnal snizhaet entropiyu diagnostiki “pochemu reshenie takoe?”.
- Skrytyy #2: (Memory ↔ Myshlenie) statistika po actions help adaptirovat politiku zapisi v pamyat.

Zemnoy abzats:
This is “avtomat s takhografom”: rulit skorostyu i pishet trek, ne menyaya rulevoe koleso (API run_rules).

# c=a+b"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_STATE_DIR = Path(os.getcwd()) / "data" / "rulehub"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_LOG = _STATE_DIR / "log.jsonl"
_STATE = _STATE_DIR / "state.json"
_FLAG = _STATE_DIR / "enable.flag"
_CFG_PATH = Path("config") / "rulehub.yaml"

def _enabled() -> bool:
    # ENV libo flag-fayl (menyaetsya iz /rulehub/toggle)
    if os.getenv("RULEHUB_ENABLED", "0").strip() == "1":
        return True
    return _FLAG.exists()

def _load_state() -> Dict[str, Any]:
    if _STATE.exists():
        try:
            return json.loads(_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"counters": {}, "last_ts": 0, "windows": {}}

def _save_state(st: Dict[str, Any]) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")

def _append_log(row: Dict[str, Any]) -> None:
    with _LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def _read_cfg() -> Dict[str, Any]:
    # minimal yaml parser: key: value; sections one deep
    if not _CFG_PATH.exists():
        return {"priorities": {}, "quotas_per_min": {}}
    cfg: Dict[str, Any] = {"priorities": {}, "quotas_per_min": {}}
    for line in _CFG_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" in s:
            k, v = s.split(":", 1)
            k = k.strip()
            v = v.strip()
            if k in ("priorities", "quotas_per_min"):
                # start the section; subsequent lines "action: N"
                continue
            if s.startswith("priorities"):
                continue
            if s.startswith("quotas_per_min"):
                continue
        # podderzhka "  action: N"
        if line.startswith("  "):
            if "priorities" not in cfg:
                cfg["priorities"] = {}
            if "quotas_per_min" not in cfg:
                cfg["quotas_per_min"] = {}
            if ":" in s:
                k, v = s.split(":", 1)
                k = k.strip()
                v = v.strip()
                try:
                    cfg["priorities"][k] = int(v)
                except Exception:
                    try:
                        cfg["quotas_per_min"][k] = int(v)
                    except Exception:
                        pass
    return cfg

def _allow_action(kind: str, st: Dict[str, Any], cfg: Dict[str, Any]) -> bool:
    # Kvota v minutu po action-kind
    q = (cfg.get("quotas_per_min") or {}).get(kind)
    if not q or q <= 0:
        return True
    now_min = int(time.time() // 60)
    win = st.setdefault("windows", {}).setdefault(str(now_min), {})
    cnt = int(win.get(kind, 0))
    if cnt >= q:
        return False
    win[kind] = cnt + 1
    # chistim starye okna
    old_keys = [k for k in st["windows"].keys() if int(k) < now_min - 5]
    for k in old_keys:
        st["windows"].pop(k, None)
    return True

def _wrap_run_rules():
    try:
        from modules import thinking_pipelines as tp  # type: ignore
    except Exception:
        return
    if not hasattr(tp, "run_rules"):
        return
    if hasattr(tp.run_rules, "_ester_rulehub_patched"):
        return
    _orig = tp.run_rules

    def run_rules_patched(rules: Dict[str, Any]) -> Any:
        if not _enabled():
            return _orig(rules)
        st = _load_state()
        cfg = _read_cfg()
        t0 = time.time()
        acts = []
        try:
            acts = [a.get("kind","") for a in (rules or {}).get("actions", [])]
        except Exception:
            acts = []
        # Let's apply quotas: if at least one action is prohibited, we will fix it and return an empty result
        blocked = [k for k in acts if not _allow_action(k, st, cfg)]
        if blocked:
            row = {
                "ts": int(t0),
                "status": "blocked",
                "blocked": blocked,
                "actions": acts,
                "input_len": len(str((rules or {}).get("input",""))),
                "duration_ms": 0,
            }
            _append_log(row)
            # increase the counters
            for k in blocked:
                st["counters"][f"blocked.{k}"] = int(st["counters"].get(f"blocked.{k}", 0)) + 1
            st["last_ts"] = int(t0)
            _save_state(st)
            return {"ok": True, "blocked": blocked}
        # Otherwise we execute the original
        try:
            res = _orig(rules)
            dur = int((time.time() - t0) * 1000)
            row = {
                "ts": int(time.time()),
                "status": "ok",
                "actions": acts,
                "input_len": len(str((rules or {}).get("input",""))),
                "duration_ms": dur,
                "result_hint": str(res)[:200]
            }
            _append_log(row)
            st["counters"]["run.ok"] = int(st["counters"].get("run.ok", 0)) + 1
            for k in acts:
                st["counters"][f"action.{k}"] = int(st["counters"].get(f"action.{k}", 0)) + 1
            st["last_ts"] = int(time.time())
            _save_state(st)
            return res
        except Exception as e:
            dur = int((time.time() - t0) * 1000)
            row = {
                "ts": int(time.time()),
                "status": "err",
                "actions": acts,
                "input_len": len(str((rules or {}).get("input",""))),
                "duration_ms": dur,
                "error": str(e)[:500]
            }
            _append_log(row)
            st["counters"]["run.err"] = int(st["counters"].get("run.err", 0)) + 1
            st["last_ts"] = int(time.time())
            _save_state(st)
            raise

    run_rules_patched._ester_rulehub_patched = True  # type: ignore[attr-defined]
    tp.run_rules = run_rules_patched  # type: ignore[assignment]

# We activate the patch immediately when importing the module (if enabled)
if _enabled():
    _wrap_run_rules()