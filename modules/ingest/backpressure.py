# -*- coding: utf-8 -*-
"""modules/ingest/backpressure.py - obedinennyy token-baket per-source: refill/burst/penalty/cooldown/queue_age, s ledger/P2P/scheduler integratsiey.

Mosty:
- Yavnyy: (Ingest/Kibernetika ↔ Spravedlivost/Nagruzka) limit per-source, refill po RPM/sec, penalty za 429/5xx/age.
- Skrytyy #1: (Nadezhnost/Monitoring ↔ Bekoff/Metriki) cooldown/cap reduce, status/counters/ages.
- Skrytyy #2: (Stoimost ↔ Byudzhet) ledger spend for penalty.
- Skrytyy #3: (Profile/Memory ↔ Prozrachnost) profile dlya blocked/penalize s teplymi notkami.

Zemnoy abzats:
Eto ne prosto regulyator, a umnyy shlagbaum Ester: propustit rovno, pritormozit nagletsov, spishet kopeyku za peregruzku, sinkhroniziruet po P2P i shepnet v profile "Ester, pipe v balanse - shag k tvoey stabilnosti v seti agentov!".

# c=a+b"""
from __future__ import annotations
import json, math, os, time
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("BP_AB", "A") or "A").upper()
DB = os.getenv("INGEST_BP_DB", "data/ingest/bp.json")
LOG = os.getenv("BP_LOG", "data/ingest/bp_log.jsonl")
ENABLED = bool(int(os.getenv("INGEST_BP_ENABLED", "1")))
DEFAULT_RPM = int(os.getenv("INGEST_BP_DEFAULT_RPM", "60"))
DEFAULT_BURST = int(os.getenv("INGEST_BP_DEFAULT_BURST", "120"))
REFILL_SEC = int(os.getenv("INGEST_BP_REFILL_SEC", "60"))
PEN_429_SEC = int(os.getenv("INGEST_BP_PENALTY_429_SEC", "120"))
PEN_5XX_SEC = int(os.getenv("INGEST_BP_PENALTY_5XX_SEC", "60"))
SOURCES_ENV = os.getenv("INGEST_BP_SOURCES", "yt:30,web:20,local:120")
P2P_SYNC = (os.getenv("BP_P2P_SYNC", "false").lower() == "true")
SEMANTIC = (os.getenv("BP_SEMANTIC", "false").lower() == "true")
AGE_THRESH = int(os.getenv("BP_AGE_THRESH", "3600"))
COST = float(os.getenv("BP_COST", "0.01"))


class AllowResult(dict):
    """Compatibility:
    - as dist: reshu"ok"sch, reshu"retro_after_sec"sch, ...
    - like stupid Legacy: ok, retro = allow(...)"""

    def __iter__(self):
        yield bool(self.get("ok", False))
        yield int(self.get("retry_after_sec") or 0)

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"cfg": {"default_rpm": DEFAULT_RPM, "default_burst": DEFAULT_BURST, "sources": _parse_sources(SOURCES_ENV)},
                   "state": {}, "queue_age": {}}, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    if not os.path.isfile(LOG): open(LOG, "w", encoding="utf-8").close()

def _load() -> Dict[str, Any]:
    _ensure()
    j = json.load(open(DB, "r", encoding="utf-8"))
    # P2P-sync: merge from peers (max ts, min cap for safety)
    if P2P_SYNC:
        try:
            from modules.p2p.sync import p2p_pull  # type: ignore
            remote = p2p_pull("ingest_bp_state") or {"state": {}}
            for k, rb in remote["state"].items():
                lb = j["state"].get(k, {})
                if rb.get("ts", 0) > lb.get("ts", 0):
                    j["state"][k] = rb
                else:
                    j["state"][k]["cap"] = min(lb.get("cap", DEFAULT_BURST), rb.get("cap", DEFAULT_BURST))  # Min cap
            _save(j)
        except Exception:
            _append_log({"ts": int(time.time()), "p2p_pull_failed": True})
    return j

def _save(j: Dict[str, Any]):
    json.dump(j, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    # P2P-push: sync state
    if P2P_SYNC:
        try:
            from modules.p2p.sync import p2p_push  # type: ignore
            p2p_push("ingest_bp_state", {"state": j["state"]})
        except Exception:
            pass

def _append_log(rec: Dict[str, Any]):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _passport(note: str, meta: Dict[str, Any]):
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm = get_mm()
        upsert_with_passport(mm, note + "- Esther, the load is balanced, a step towards your stability in the agent network!", meta, source="ingest://backpressure")
    except Exception:
        _append_log({"ts": int(time.time()), "passport_failed": note})

def _parse_sources(s: str) -> Dict[str, int]:
    out = {}
    for part in (s or "").split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = max(1, int(v.strip() or "0"))
    return out

def _now() -> float:
    return time.time()

def _bucket_for(source: str) -> Tuple[str, int]:
    if SEMANTIC:
        # Lightweight semantic grouping by source name.
        if "yt" in source.lower(): return "yt", DEFAULT_RPM // 2
        if "web" in source.lower(): return "web", DEFAULT_RPM // 3
    cfg = _load()["cfg"]
    for k in cfg["sources"]:
        if source.startswith(k): return k, cfg["sources"][k]
    return "default", cfg["default_rpm"]

def _blocked(b: Dict[str, Any]) -> int:
    return max(0, int(b.get("blocked_until", 0) - _now()))

def allow(source: str, cost: float = 1.0) -> Dict[str, Any]:
    if AB == "B":
        return AllowResult({"ok": True, "dry_run": True, "retry_after_sec": 0})
    j = _load()
    enabled = bool(j.get("cfg", {}).get("enabled", ENABLED))
    if not enabled:
        return AllowResult({"ok": True, "tokens_left": 999, "retry_after_sec": 0})
    state = j["state"]
    key, rpm = _bucket_for(source)
    burst = j["cfg"].get("default_burst", DEFAULT_BURST)
    b = state.get(key, {"tokens": float(burst), "last": _now(), "blocked_until": 0, "cap": burst, "ts": int(time.time())})
    now = _now()
    # Refill
    elapsed = now - b["last"]
    b["last"] = now
    b["tokens"] = min(b["cap"], b["tokens"] + elapsed * (rpm / 60.0))
    if now < b["blocked_until"]:
        _append_log({"ts": int(now), "blocked": key})
        return AllowResult({"ok": False, "reason": "blocked", "retry_after_sec": _blocked(b)})
    if b["tokens"] < cost:
        _append_log({"ts": int(now), "no_tokens": key})
        need = cost - b["tokens"]
        sec = math.ceil(need / (rpm / 60.0))
        return AllowResult({"ok": False, "reason": "no_tokens", "retry_after_sec": max(1, sec), "tokens": round(b["tokens"], 2)})
    # Consume
    b["tokens"] -= cost
    b["ts"] = int(now)
    state[key] = b
    _save(j)
    return AllowResult({"ok": True, "tokens_left": round(b["tokens"], 2), "rpm": rpm, "source": key, "retry_after_sec": 0})

def penalize(source: str, code: int | None = None, seconds: int | None = None) -> Dict[str, Any]:
    j = _load()
    state = j["state"]
    key, rpm = _bucket_for(source)
    b = state.get(key, {"tokens": float(DEFAULT_BURST), "last": _now(), "blocked_until": 0, "cap": DEFAULT_BURST, "ts": int(time.time())})
    add = seconds or (PEN_429_SEC if code == 429 else PEN_5XX_SEC if code and code >= 500 else 60)
    b["blocked_until"] = max(b.get("blocked_until", 0), _now() + add)
    b["cap"] = max(5, int(b.get("cap", DEFAULT_BURST) * 0.8))  # Reduce cap
    b["ts"] = int(time.time())
    state[key] = b
    _save(j)
    _passport("Backpressure penalized", {"source": key, "code": code, "seconds": add})
    _append_log({"ts": int(time.time()), "penalize": {"source": key, "code": code, "add_sec": add}})
    _ledger_reserve_spend(COST, f"ingest_penalty_{key}", True)
    return {"ok": True, "source": key, "blocked_for_sec": _blocked(b)}

def record_result(source: str, ok: bool, http_code: int | None = None) -> None:
    if not ok or (http_code and (http_code >= 500 or http_code == 429)):
        penalize(source, http_code)
    else:
        j = _load()
        state = j["state"]
        key, rpm = _bucket_for(source)
        b = state.get(key, {})
        b["cap"] = min(DEFAULT_BURST, int(b.get("cap", DEFAULT_BURST) * 1.05))  # Restore cap
        _save(j)

def set_queue_age(key: str, created_ts: int) -> None:
    j = _load()
    j["queue_age"][key] = int(created_ts)
    _save(j)

def auto_slowdown() -> None:
    j = _load()
    now = _now()
    for k, ts in j.get("queue_age", {}).items():
        if now - ts > AGE_THRESH:
            penalize(k, seconds=300)  # 5 min slowdown
            _passport("Auto slowdown by queue age", {"key": k, "age": now - ts})

def status() -> Dict[str, Any]:
    j = _load()
    now = _now()
    st = {}
    for k, b in j["state"].items():
        st[k] = {"tokens": round(b.get("tokens", 0), 2), "blocked_for_sec": _blocked(b), "last": int(b.get("last", 0)), "cap": b.get("cap", DEFAULT_BURST)}
    ages = {k: int(now - v) for k, v in j.get("queue_age", {}).items()}
    return {"ok": True, "cfg": j["cfg"], "state": st, "queue_ages": ages, "counters": counters()}

def counters() -> Dict[str, Any]:
    j = _load()
    queue_age = dict(j.get("queue_age") or {})
    ingest_queue = int(len(queue_age))
    last_ingest_ts = int(max(queue_age.values()) if queue_age else 0)

    queue_dir = os.getenv("INGEST_QUEUE_DIR", "data/ingest/queue")
    bytes_pending = 0
    try:
        if os.path.isdir(queue_dir):
            for fn in os.listdir(queue_dir):
                fp = os.path.join(queue_dir, fn)
                if os.path.isfile(fp):
                    bytes_pending += int(os.path.getsize(fp))
    except Exception:
        bytes_pending = 0

    allowed = 0
    blocked = 0
    drops = 0
    try:
        if os.path.isfile(LOG):
            with open(LOG, "r", encoding="utf-8") as f:
                lines = f.readlines()[-2000:]
            for line in lines:
                row = line.strip()
                if not row:
                    continue
                try:
                    obj = json.loads(row)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                if "blocked" in obj or "no_tokens" in obj:
                    blocked += 1
                    drops += 1
                if "penalize" in obj:
                    drops += 1
                if obj.get("allow_ok") is True:
                    allowed += 1
    except Exception:
        pass

    return {
        "ok": True,
        "ingest_queue": int(ingest_queue),
        "bytes_pending": int(bytes_pending),
        "last_ingest_ts": int(last_ingest_ts),
        "drops": int(drops),
        "allowed": int(allowed),
        "blocked": int(blocked),
    }

def get_config() -> Dict[str, Any]:
    j = _load()
    return {"ok": True, **j["cfg"]}

def set_config(default_rpm: int | Dict[str, Any] | None = None, sources: Dict[str, int] | None = None) -> Dict[str, Any]:
    if not _check_rbac(["admin"]): return {"ok": False, "error": "rbac_forbidden"}
    j = _load()
    # Legacy-sovmestimost: set_config({...})
    if isinstance(default_rpm, dict) and sources is None:
        cfg = dict(default_rpm)
        rpm = cfg.get("default_rpm")
        if rpm is None and cfg.get("default_rps") is not None:
            rpm = max(1, int(round(float(cfg.get("default_rps")) * 60.0)))
        if rpm is not None:
            j["cfg"]["default_rpm"] = int(rpm)
        if cfg.get("default_burst") is not None:
            j["cfg"]["default_burst"] = max(1, int(cfg.get("default_burst")))
        if cfg.get("enabled") is not None:
            j["cfg"]["enabled"] = bool(cfg.get("enabled"))
        src = cfg.get("sources")
        if isinstance(src, dict):
            for k, v in src.items():
                j["cfg"]["sources"][str(k)] = max(1, int(v))
    elif default_rpm is not None:
        j["cfg"]["default_rpm"] = int(default_rpm)
    if sources:
        for k, v in sources.items():
            j["cfg"]["sources"][str(k)] = max(1, int(v))
    _save(j)
    return {"ok": True, "cfg": j["cfg"]}

def refill_all(params: Dict[str, Any]) -> Dict[str, Any]:
    j = _load()
    now = _now()
    for k, b in j["state"].items():
        elapsed = now - b["last"]
        rpm = _bucket_for(k)[1]
        b["tokens"] = min(b["cap"], b["tokens"] + elapsed * (rpm / 60.0))
        b["last"] = now
        if now > b["blocked_until"]: b["blocked_until"] = 0
    _save(j)
    auto_slowdown()
    _passport("Backpressure refilled", {"sources": len(j["state"])})
    return {"ok": True, "refilled": len(j["state"])}

def _check_rbac(required: List[str]) -> bool:
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role(required)
    except Exception:
        return True

def register(app):
    from flask import Blueprint, request, jsonify
    bp_ingest = Blueprint("ingest_bp", __name__)
    @bp_ingest.route("/ingest/bp/status", methods=["GET"])
    def bp_status():
        if not _check_rbac(["viewer", "operator", "admin"]): return jsonify({"ok": False, "error": "rbac_forbidden"}), 403
        return jsonify(status())
    @bp_ingest.route("/ingest/bp/set_config", methods=["POST"])
    def bp_set_config():
        d = request.get_json() or {}
        return jsonify(set_config(d.get("default_rpm"), d.get("sources")))
    app.register_blueprint(bp_ingest)
    # Scheduler add
    try:
        from modules.cron.scheduler import add_task  # type: ignore
        add_task("ingest_bp_refill", {"cron": "@hourly"}, "ingest.bp.refill_all", {})
    except Exception:
        pass
    return app
