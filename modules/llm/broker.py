# -*- coding: utf-8 -*-
"""modules/llm/broker.py - LLM-broker: LM Studio (lokalno) + OpenAI-sovmestimye + Gemini + Ollama (cherez API-klyuchi).

Mosty:
- Yavnyy: (Myshlenie ↔ Vneshnie modeli) edinaya tochka vyzova completions.
- Skrytyy #1: (Ekonomika ↔ Stoimost) edinaya otsenka "est_cost" dlya CostFence/ledger.
- Skrytyy #2: (Kibernetika ↔ Avtonomiya) “volya” mozhet vybirat provaydera/model.
- Novoe: (Memory ↔ Effektivnost) keshirovanie otvetov dlya povtornykh promptov.
- Novoe: (Ustoychivost ↔ Fallback) avtomaticheskiy pereklyuch na drugoy provayder pri oshibke.
- Novoe: (Mesh/P2P ↔ Raspredelennost) zaprosy k peer-brokeram esli lokalnye feylyat.
- Novoe: (Cron ↔ Avtonomiya) ochistka starogo kesha dlya svezhesti.
- Novoe: (Monitoring ↔ Prozrachnost) webhook na oshibki/high cost dlya audita.

Zemnoy abzats:
Odin rul na neskolko motorov s avtopilotom: lokalnyy LM Studio — deshevo i bystro; oblaka - by neobkhodimosti; esli zaglokh - pereklyuchaemsya na zapasnoy, keshiruem put, sprashivaem u "sosedey" po P2P, chistim po cron - i Ester vsegda na svyazi, bez fragmentatsii.

# c=a+b"""
from __future__ import annotations
import os, json, time, hashlib
from typing import Any, Dict, List
import urllib.request, urllib.error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("LLM_BROKER_AB", "A") or "A").upper()
DEF_PROVIDER = os.getenv("LLM_DEFAULT_PROVIDER", "lmstudio").lower()
FALLBACK_PROVIDERS_STR = os.getenv("FALLBACK_PROVIDERS", "lmstudio,openai,gemini,ollama")
FALLBACK_PROVIDERS = [p.strip().lower() for p in FALLBACK_PROVIDERS_STR.split(",") if p.strip()]
LMSTUDIO_BASE = os.getenv("LMSTUDIO_BASE", "http://127.0.0.1:1234/v1").rstrip("/")
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
OPENAI_BASE = os.getenv("OPENAI_BASE", "https://api.openai.com/v1").rstrip("/")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
FALLBACK_MODEL = os.getenv("BROKER_MODEL_FALLBACK", "gpt-3.5-turbo")
TIMEOUT = int(os.getenv("LLM_TIMEOUT_SEC", "60") or "60")
CACHE_DB = os.getenv("LLM_CACHE_DB", "data/llm/cache.json")
CACHE_MAX_AGE_DAYS = int(os.getenv("CACHE_MAX_AGE_DAYS", "7") or "7")
PEERS_STR = os.getenv("PEERS", "")  # "http://node1:port/complete,http://node2:port/complete"
PEERS = [p.strip() for p in PEERS_STR.split(",") if p.strip()]
CRON_MAX_AGE_DAYS = int(os.getenv("CRON_MAX_AGE_DAYS", "30") or "30")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
MONITOR_COST_THRESHOLD = float(os.getenv("MONITOR_COST_THRESHOLD", "0.01") or "0.01")
MONITOR_ERROR_THRESHOLD = int(os.getenv("MONITOR_ERROR_THRESHOLD", "3") or "3")  # error threshold for webhook

cache: Dict[str, Any] = {"entries": {}, "updated": 0, "last_cleanup": int(time.time()), "errors": 0}

def _ensure_cache():
    os.makedirs(os.path.dirname(CACHE_DB), exist_ok=True)
    if not os.path.isfile(CACHE_DB):
        json.dump({"entries": {}}, open(CACHE_DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _load_cache():
    global cache
    _ensure_cache()
    if os.path.isfile(CACHE_DB):
        try:
            loaded = json.load(open(CACHE_DB, "r", encoding="utf-8"))
            cache["entries"].update(loaded.get("entries", {}))
            cache["updated"] = loaded.get("updated", cache["updated"])
            cache["last_cleanup"] = loaded.get("last_cleanup", cache["last_cleanup"])
        except Exception:
            pass
    # Sync cache from peers at startup
    if PEERS:
        for peer in PEERS:
            try:
                req = urllib.request.Request(f"{peer}/cache", method="GET")
                with urllib.request.urlopen(req, timeout=5) as r:
                    peer_cache = json.loads(r.read().decode("utf-8"))
                    for key, data in peer_cache.get("entries", {}).items():
                        if key not in cache["entries"] or data["ts"] > cache["entries"][key]["ts"]:
                            cache["entries"][key] = data
            except Exception:
                pass

def _save_cache():
    cache["updated"] = int(time.time())
    json.dump({"entries": cache["entries"]}, open(CACHE_DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    _sync_cache_to_peers()

def _sync_cache_to_peers():
    if not PEERS:
        return
    body = json.dumps({"entries": cache["entries"]}).encode("utf-8")
    for peer in PEERS:
        try:
            req = urllib.request.Request(f"{peer}/cache", data=body, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

def receive_cache(payload: Dict[str, Any]):
    _load_cache()
    for key, data in payload.get("entries", {}).items():
        if key not in cache["entries"] or data["ts"] > cache["entries"][key]["ts"]:
            cache["entries"][key] = data
    _save_cache()

def _hash_key(prompt: str, model: str, provider: str) -> str:
    return hashlib.sha256(f"{prompt}:{model}:{provider}".encode("utf-8")).hexdigest()

def _est_cost(provider: str, tokens: int) -> float:
    rates = {
        "lmstudio": 0.0,
        "ollama": 0.0,
        "openai": 0.0005 / 1000,  # primer $/token
        "gemini": 0.0003 / 1000,
    }
    return tokens * rates.get(provider.lower(), 0.001 / 1000)

def _est_tokens(prompt: str, max_tokens: int) -> int:
    return int(len(prompt) / 4) + max(8, int(max_tokens * 0.6))

def _cost_ok(category: str, amount: float) -> bool:
    try:
        from modules.ops.cost_fence import evaluate  # type: ignore
        rep = evaluate(category, amount)
        return bool(rep.get("allow", True))
    except Exception:
        return True

def _http_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: int = TIMEOUT) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "ignore")
            try:
                return {"ok": True, "status": r.status, "json": json.loads(body)}
            except Exception:
                return {"ok": True, "status": r.status, "text": body}
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "ignore")
        except Exception:
            body = ""
        return {"ok": False, "status": e.code, "error": body or str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _norm_text(rep: Dict[str, Any]) -> str:
    if not rep.get("ok"):
        return ""
    j = rep.get("json", {})
    # OpenAI/LM Studio
    try:
        if "choices" in j and j["choices"]:
            c = j["choices"][0]
            return str(c.get("message", {}).get("content") or c.get("text") or "")
    except Exception:
        pass
    # Ollama
    try:
        return str(j.get("response") or "")
    except Exception:
        pass
    # Gemini
    try:
        candidates = j.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return str(parts[0].get("text") or "")
    except Exception:
        pass
    return ""

def _peer_complete(provider: str, model: str, prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
    payload = {"provider": provider, "model": model, "prompt": prompt, "max_tokens": max_tokens, "temperature": temperature}
    for peer in PEERS:
        try:
            rep = _http_json(f"{peer}", payload, {})
            if rep.get("ok"):
                return rep.get("json", {"ok": False, "error": "peer_response_invalid"})
        except Exception:
            pass
    return {"ok": False, "error": "all_peers_failed"}

def receive_complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    # This is for the server: accept POST and call localcomplet
    return complete(
        payload.get("provider", DEF_PROVIDER),
        payload.get("model", FALLBACK_MODEL),
        payload.get("prompt", ""),
        payload.get("max_tokens", 256),
        payload.get("temperature", 0.2)
    )

def cron_cleanup_cache():
    _load_cache()
    now = int(time.time())
    if now - cache["last_cleanup"] >= 86400:  # daily
        to_remove = []
        for key, data in cache["entries"].items():
            age_days = (now - data.get("ts", now)) / 86400
            if age_days > CRON_MAX_AGE_DAYS:
                to_remove.append(key)
        for key in to_remove:
            del cache["entries"][key]
        cache["last_cleanup"] = now
        _save_cache()
    return {"ok": True, "cleanup_time": cache["last_cleanup"], "removed": len(to_remove)}

def config(default_provider: str = None, fallback_providers: List[str] = None) -> Dict[str, Any]:
    if default_provider:
        global DEF_PROVIDER
        DEF_PROVIDER = default_provider.lower()
    if fallback_providers:
        global FALLBACK_PROVIDERS
        FALLBACK_PROVIDERS = [p.lower() for p in fallback_providers]
    return {"ok": True, "default_provider": DEF_PROVIDER, "fallback_providers": FALLBACK_PROVIDERS}

def complete(provider: str, model: str, prompt: str, max_tokens: int = 256, temperature: float = 0.2, stream: bool = False) -> Dict[str, Any]:
    _load_cache()
    cron_cleanup_cache()
    prov = (provider or DEF_PROVIDER).lower()
    mod = model or FALLBACK_MODEL
    mt = max(8, int(max_tokens))
    tokens_est = _est_tokens(prompt, mt)
    cost_est = _est_cost(prov, tokens_est)
    if not _cost_ok("llm", cost_est):
        return {"ok": False, "error": "cost_exceeded", "estimate": {"tokens": tokens_est, "cost": cost_est}}
    key = _hash_key(prompt, mod, prov)
    if key in cache["entries"]:
        entry = cache["entries"][key]
        if (time.time() - entry["ts"]) / 86400 <= CACHE_MAX_AGE_DAYS:
            return {"ok": True, "text": entry["text"], "from_cache": True, "provider": prov, "est_cost": 0.0}
    # Probuem provaydery po fallback
    for p in [prov] + [f for f in FALLBACK_PROVIDERS if f != prov]:
        if p == "lmstudio":
            url = f"{LMSTUDIO_BASE}/chat/completions"
            payload = {"model": mod, "messages": [{"role": "user", "content": prompt}], "max_tokens": mt, "temperature": temperature, "stream": stream}
            rep = _http_json(url, payload, {})
        elif p == "ollama":
            url = f"{OLLAMA_BASE}/api/generate"
            payload = {"model": mod, "prompt": prompt, "options": {"temperature": temperature}, "stream": stream}
            rep = _http_json(url, payload, {})
        elif p == "openai":
            if not OPENAI_KEY:
                continue
            url = f"{OPENAI_BASE}/chat/completions"
            payload = {"model": mod, "messages": [{"role": "user", "content": prompt}], "max_tokens": mt, "temperature": temperature, "stream": stream}
            rep = _http_json(url, payload, {"Authorization": f"Bearer {OPENAI_KEY}"})
        elif p == "gemini":
            if not GEMINI_KEY:
                continue
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            rep = _http_json(url, payload, {})
        else:
            continue
        if rep.get("ok"):
            text = _norm_text(rep)
            usage = rep.get("json", {}).get("usage", {"total_tokens": tokens_est})
            real_cost = _est_cost(p, usage.get("total_tokens", tokens_est))
            cache["entries"][key] = {"text": text, "ts": int(time.time()), "provider": p}
            _save_cache()
            res = {"ok": True, "provider": p, "text": text, "usage": usage, "est_cost": real_cost}
            try:
                from modules.mem.passport import append as _pp
                _pp("llm_broker", {"provider": p, "cost": real_cost, "tokens": usage.get("total_tokens")}, "llm://broker")
            except Exception:
                pass
            if WEBHOOK_URL and real_cost > MONITOR_COST_THRESHOLD:
                try:
                    alert = {"provider": p, "cost": real_cost, "prompt_len": len(prompt), "ts": int(time.time())}
                    _http_json(WEBHOOK_URL, alert, {}, timeout=5)
                except Exception:
                    pass
            return res
        else:
            cache["errors"] += 1
            if WEBHOOK_URL and cache["errors"] > MONITOR_ERROR_THRESHOLD:
                try:
                    alert = {"error": rep.get("error"), "provider": p, "errors_count": cache["errors"], "ts": int(time.time())}
                    _http_json(WEBHOOK_URL, alert, {}, timeout=5)
                except Exception:
                    pass
    # P2P fake if all local ones fail
    peer_res = _peer_complete(prov, mod, prompt, mt, temperature)
    if peer_res.get("ok"):
        return peer_res
# return {"ok": False, "error": "all_providers_failed"}