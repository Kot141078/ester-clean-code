# -*- coding: utf-8 -*-
"""
modules/chat_api.py — REST-vkhod dlya chata (vnutri proekta Ester/Liah)

Zadacha fayla: dat edinyy HTTP endpoint, kotoryy:
- sobiraet sistemnyy prompt (profile + tekuschee vremya + RAG-fragmenty),
- akkuratno rezhet kontekst (chtoby lokalnaya model ne umirala),
- vyzyvaet lokalnyy OpenAI-compatible endpoint (LM Studio / Ollama OpenAI / vLLM),
- vozvraschaet otvet i (po vozmozhnosti) podpis provaydera.

YaVNYY MOST: c=a+b — chelovek zadaet vopros, LLM-protsedury derzhat formu (limiter/pamyat/vremya).
SKRYTYE MOSTY:
  - Ashby: variety — rezhem shum, no ostavlyaem raznoobrazie (istoriya+RAG) v dopustimykh granitsakh.
  - Cover&Thomas: ogranichenie kanala — byudzhetiruem kontekst/tokeny, inache kanal «zabivaetsya».
ZEMNOY ABZATs:
  Kontekst — kak obem legkikh: vdokhnut mozhno mnogo, no esli pytatsya vdokhnut «vse srazu»,
  nachinaetsya kashel (truncation/oshibka). Limiter — eto diafragma: doziruet vozdukh, chtoby zhit.

PATCh 2026-02-09 (v2):
  - SYSTEM_PROMPT zamenen na identity_anchor.build_system_prompt()
  - Profile chitaetsya cherez identity_anchor.load_passport()
  - HARD_PROMPT_CHARS podnyat do 24000
  - Ubran random-fallback iz recall (teper pustaya pamyat = chestnoe «Pusto»)
"""

from __future__ import annotations

import os
import json
import time
import sys
import zlib
import asyncio
import importlib
import logging
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- PATCh: import edinogo yakorya identichnosti ---
try:
    from modules.identity_anchor import (
        build_system_prompt,
        load_passport,
        ESTER_CORE_IDENTITY,
    )
    _HAS_ANCHOR = True
except ImportError:
    _HAS_ANCHOR = False
    logging.warning("[chat_api] identity_anchor not found — using legacy fallback")


bp = Blueprint("chat_api", __name__)

# ---- Konfig ----
LMSTUDIO_URL = os.getenv("LMSTUDIO_URL", "http://127.0.0.1:1234/v1/chat/completions").strip()
TIMEOUT = float(os.getenv("REST_TIMEOUT", "120"))

# LEGACY fallback — ispolzuetsya TOLKO esli identity_anchor nedostupen
_LEGACY_SYSTEM_PROMPT = os.getenv(
    "REST_SYSTEM_PROMPT",
    (
        "You are the configured digital entity. Owner profile is provided by Web UI.\n"
        "Otvechay po-russki, teplo i po delu.\n"
        "Esli ne pomnish — skazhi chestno, NE VYDUMYVAY.\n"
        "Ne obrezay otvet, pishi do kontsa."
    ),
)

# Byudzhety vstavok
MAX_HISTORY_CHARS = int(os.getenv("REST_MAX_HISTORY_CHARS", "30000"))
PASSPORT_MAX_CHARS = int(os.getenv("REST_PASSPORT_MAX_CHARS", "30000"))
RAG_MAX_CHARS = int(os.getenv("REST_RAG_MAX_CHARS", "30000"))

# Zhestkiy obschiy limit na SUMMARNYY prompt (system+history+user).
# PATCh: podnyat s 12000 do 24000 — inache Ester zadykhaetsya.
HARD_PROMPT_CHARS = int(os.getenv("REST_HARD_PROMPT_CHARS", "35000"))

PASSPORT_PATH = os.getenv("REST_PASSPORT_PATH", os.path.join("data", "passport", "passport.txt"))
RAG_CONTEXT_PATH = os.getenv("REST_RAG_CONTEXT_PATH", os.path.join("data", "passport", "rag_context.txt"))
CLEAN_MEMORY_PATH = os.getenv("REST_CLEAN_MEMORY_PATH", os.path.join("data", "passport", "clean_memory.jsonl"))

# CLOSED_BOX (po umolchaniyu True — kak u tebya)
CLOSED_BOX = os.getenv("CLOSED_BOX", "1").strip() in ("1", "true", "yes", "True")

HEADERS = {"Content-Type": "application/json"}


# ---- Vspomogatelnoe ----
def _read_text(path: str, max_chars: int) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace").strip()[:max_chars]
    except Exception as e:
        logging.warning(f"[chat_api] read failed: {p} -> {e}")
        return ""


def _format_time_for_prompt() -> str:
    try:
        import time_utils  # type: ignore
        _, human = time_utils.format_for_prompt()
        return human
    except Exception:
        return time.strftime("%Y-%m-%d %H:%M:%S")


def _trim_history(messages: List[Dict[str, str]], max_chars: int) -> List[Dict[str, str]]:
    """Obrezaem istoriyu po simvolam (bystro i predskazuemo).
    Sokhranyaem system i poslednie soobscheniya, poka ne vlezem v byudzhet.
    """
    if not messages:
        return []

    sys = messages[0] if messages[0].get("role") == "system" else None
    tail = messages[1:] if sys else messages[:]

    out: List[Dict[str, str]] = []
    total = 0

    for m in reversed(tail):
        c = (m.get("content") or "")
        sz = len(c)
        if total + sz > max_chars and out:
            break
        out.append({"role": m.get("role", "user"), "content": c})
        total += sz

    out.reverse()
    if sys:
        return [sys] + out
    return out


def _looks_like_context_overflow(err_text: str) -> bool:
    s = (err_text or "").lower()
    needles = [
        "context length",
        "maximum context",
        "max context",
        "too many tokens",
        "token limit",
        "prompt is too long",
        "n_ctx",
        "exceeded",
        "overload context",
    ]
    return any(n in s for n in needles)


def _messages_total_chars(messages: List[Dict[str, str]]) -> int:
    return sum(len((m.get("content") or "")) for m in messages)


def _call_llm(model: str, messages: List[Dict[str, str]], *, temperature: float) -> Tuple[str, str]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    mt = os.getenv("REST_MAX_TOKENS", "").strip()
    if mt:
        try:
            payload["max_tokens"] = int(mt)
        except Exception:
            pass

    try:
        r = requests.post(LMSTUDIO_URL, headers=HEADERS, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return (text or "").strip(), ""
    except Exception as e:
        return "", str(e)


def _save_clean_memory(user_text: str, assistant_text: str) -> None:
    try:
        p = Path(CLEAN_MEMORY_PATH)
        p.parent.mkdir(parents=True, exist_ok=True)
        obj = {"ts": time.time(), "user": user_text, "assistant": assistant_text}
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception as e:
        logging.warning(f"[chat_api] clean_memory write failed: {e}")


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
        return bool(default)
    return v in ("1", "true", "yes", "on", "y")


def _stable_chat_id(raw_sid: str) -> int:
    sid = str(raw_sid or "web-ui").strip() or "web-ui"
    if sid.lstrip("-").isdigit():
        try:
            return int(sid)
        except Exception:
            pass
    # Stable numeric id for web sessions so ester_arbitrage can reuse short-term memory buckets.
    return int(900000000 + (zlib.adler32(sid.encode("utf-8")) % 100000000))


def _run_coro_sync(coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Fallback: if an event loop is already running in this thread.
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            try:
                loop.close()
            except Exception:
                pass


def _call_main_live_arbitrage(
    *,
    text: str,
    sid: str,
    user_id: str,
    user_name: str,
    chat_id: int,
    address_as: str,
    tone_context: str = "",
    file_context: str = "",
) -> Tuple[str, str]:
    """Try to call run_ester_fixed.ester_arbitrage (same live contour as Telegram)."""
    main_mod = sys.modules.get("__main__")
    run_mod = sys.modules.get("run_ester_fixed")
    if run_mod is None:
        try:
            run_mod = importlib.import_module("run_ester_fixed")
        except Exception:
            run_mod = None

    arb = None
    run_sync = None
    for mod in (main_mod, run_mod):
        if mod is None:
            continue
        fn = getattr(mod, "ester_arbitrage", None)
        if callable(fn):
            arb = fn
            run_sync = getattr(mod, "_run_coro_sync", None)
            break

    if not callable(arb):
        return "", ""
    try:
        coro = arb(
            user_text=str(text or ""),
            user_id=str(user_id or sid or "web"),
            user_name=str(user_name or "WebUser"),
            chat_id=int(chat_id),
            address_as=str(address_as or user_name or "Polzovatel"),
            tone_context=str(tone_context or ""),
            file_context=str(file_context or ""),
        )
        out = run_sync(coro) if callable(run_sync) else _run_coro_sync(coro)
        txt = str(out or "").strip()
        if txt:
            return txt, "hivemind"
    except Exception as e:
        logging.warning(f"[chat_api] live arbitrage failed: {e}")
    return "", ""


# ---------------------------------------------------------------------------
#  PATCh: build_system_prompt cherez identity_anchor
# ---------------------------------------------------------------------------

def _build_system_prompt_full(
    *,
    passport_max: int = PASSPORT_MAX_CHARS,
    rag_max: int = RAG_MAX_CHARS,
) -> str:
    """
    Sobiraet system prompt.
    Esli identity_anchor dostupen — cherez nego (polnaya identichnost).
    Inache — legacy (obednennyy, no uzhe ne golaya stroka).
    """
    passport = ""
    rag = ""

    if _HAS_ANCHOR:
        passport = load_passport(max_chars=passport_max)
    else:
        passport = _read_text(PASSPORT_PATH, passport_max)

    rag = _read_text(RAG_CONTEXT_PATH, rag_max)

    if _HAS_ANCHOR:
        return build_system_prompt(
            passport_text=passport,
            memory_fragments=rag,
            closed_box=CLOSED_BOX,
        )

    # --- LEGACY fallback (esli identity_anchor ne importirovan) ---
    human_t = _format_time_for_prompt()
    sys_prompt = _LEGACY_SYSTEM_PROMPT
    if passport:
        sys_prompt += "\n\n[PASPORT]\n" + passport + "\n"
    sys_prompt += f"\n\n[SYSTEM REALTIME]\nData/vremya (UTC): {human_t}\n"
    sys_prompt += "VAZhNO: vremya i datu brat TOLKO iz stroki vyshe.\n"
    if rag:
        sys_prompt += "\n[PAMYaT]\n" + rag + "\n"
    else:
        sys_prompt += "\n[PAMYaT]\nPusto\n"
    return sys_prompt


def _shrink_system_prompt_v2(
    *,
    passport_keep: int,
    rag_keep: int,
) -> str:
    """Peresobiraet system prompt s urezannymi byudzhetami."""
    return _build_system_prompt_full(
        passport_max=max(400, passport_keep),
        rag_max=max(200, rag_keep),
    )


def _build_messages_for_llm(
    message: str,
    history: List[Dict[str, str]],
    *,
    max_history_chars: int,
    passport_max: int,
    rag_max: int,
) -> List[Dict[str, str]]:
    sys_prompt = _build_system_prompt_full(
        passport_max=passport_max,
        rag_max=rag_max,
    )

    sys_msg = {"role": "system", "content": sys_prompt}

    msgs = _trim_history([sys_msg] + (history or []), max_chars=max_history_chars)
    msgs.append({"role": "user", "content": message})
    return msgs


def _enforce_hard_budget(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Garantiruet, chto summarnyy prompt ne razduetsya.
    Esli slishkom bolshoy — rezhem istoriyu, zatem umenshaem profile/rag.
    """
    total = _messages_total_chars(messages)
    if total <= HARD_PROMPT_CHARS:
        return messages

    # 1) Snachala rezhem istoriyu silnee (v 2 raza)
    sys = messages[0] if messages and messages[0].get("role") == "system" else None
    tail = messages[1:] if sys else messages[:]
    user_msg = tail[-1] if tail else {"role": "user", "content": ""}

    history_only = tail[:-1]
    shrunk = _trim_history(([sys] if sys else []) + history_only, max_chars=max(2000, MAX_HISTORY_CHARS // 2))
    msgs2 = shrunk + [user_msg]
    if _messages_total_chars(msgs2) <= HARD_PROMPT_CHARS:
        return msgs2

    # 2) Peresobiraem system prompt s menshim profileom/ragom
    sys2 = _shrink_system_prompt_v2(
        passport_keep=max(1500, PASSPORT_MAX_CHARS // 3),
        rag_keep=max(800, RAG_MAX_CHARS // 3),
    )
    sys_msg2 = {"role": "system", "content": sys2}
    msgs3 = _trim_history([sys_msg2] + history_only, max_chars=max(1500, MAX_HISTORY_CHARS // 3)) + [user_msg]
    if _messages_total_chars(msgs3) <= HARD_PROMPT_CHARS:
        return msgs3

    # 3) Posledniy shag — sovsem zhestko
    sys3 = _shrink_system_prompt_v2(
        passport_keep=800,
        rag_keep=400,
    )
    sys_msg3 = {"role": "system", "content": sys3}
    msgs4 = _trim_history([sys_msg3] + history_only, max_chars=1200) + [user_msg]
    return msgs4


# ---------- Publichnaya funktsiya dlya vyzova iz run_ester_fixed.py (bez HTTP) ----------
def handle_message(
    text: str,
    history: Optional[List[Dict[str, str]]] = None,
    engine: Optional[str] = None,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """Lokalnyy obrabotchik soobscheniya.
    Vozvraschaet dict: {ok, reply, provider, engine}
    """
    message = (text or "").strip()
    if not message:
        return {"ok": False, "error": "empty message"}

    # "ruchnoy rychag"
    if message.lower() in ("sozhmi istoriyu", "/compress", "/compact"):
        return {
            "ok": True,
            "reply": "Ok. Dalshe budu rezat istoriyu i sistemnye vstavki zhestche. Teper sprosi esche raz koroche.",
            "provider": "SYSTEM",
            "engine": engine or os.getenv("REST_ENGINE", "local-model"),
        }

    model = (engine or os.getenv("REST_ENGINE", "local-model")).strip()
    temp = float(temperature if temperature is not None else os.getenv("REST_TEMPERATURE", "0.6"))

    hist = history if isinstance(history, list) else []

    # 1) sobiraem soobscheniya
    messages = _build_messages_for_llm(
        message,
        hist,
        max_history_chars=MAX_HISTORY_CHARS,
        passport_max=PASSPORT_MAX_CHARS,
        rag_max=RAG_MAX_CHARS,
    )
    messages = _enforce_hard_budget(messages)

    # 2) osnovnoy vyzov
    answer, err = _call_llm(model, messages, temperature=temp)

    # 3) retry pri yavnom overflow
    if (not answer) and err and _looks_like_context_overflow(err):
        logging.warning(f"[chat_api] overflow -> retry: {err}")
        messages2 = _build_messages_for_llm(
            message,
            hist,
            max_history_chars=max(2000, MAX_HISTORY_CHARS // 2),
            passport_max=max(1500, PASSPORT_MAX_CHARS // 2),
            rag_max=max(800, RAG_MAX_CHARS // 2),
        )
        messages2 = _enforce_hard_budget(messages2)
        answer, err = _call_llm(model, messages2, temperature=temp)

    if not answer:
        logging.warning(f"[chat_api] LLM error: {err}")
        answer = (
            "Izvini, ya ne smogla otvetit: libo kontekst slishkom bolshoy, libo provayder dal sboy.\n"
            "Sdelay tak:\n"
            "1) Pereformuliruy koroche, ili\n"
            "2) napishi: «sozhmi istoriyu», ili\n"
            "3) prover, chto lokalnaya model dostupna (LM Studio/Ollama endpoint)."
        )
        provider = "ERROR"
    else:
        provider = "LOCAL"

    _save_clean_memory(message, answer)
    return {"ok": True, "reply": answer, "provider": provider, "engine": model}


# ----------------------------- HTTP endpoint (Flask) -----------------------------
@bp.route("/ester/chat/message", methods=["POST"])
@bp.route("/chat/message", methods=["POST"])
def chat_entry():
    try:
        data = request.get_json(force=True, silent=True) or {}
        message = (data.get("text") or data.get("message") or "").strip()
        history = data.get("history") or []
        engine = (data.get("engine") or None)
        mode = (data.get("mode") or engine or "").strip()
        sid = str(data.get("sid") or data.get("session_id") or data.get("chat_id") or "web-ui").strip() or "web-ui"
        user_id = str(data.get("user_id") or data.get("uid") or sid or "web").strip() or "web"
        user_name = str(data.get("user_name") or data.get("user") or "WebUser").strip() or "WebUser"
        address_as = str(data.get("address_as") or user_name).strip() or user_name
        tone_context = str(data.get("tone_context") or "").strip()
        file_context = str(data.get("file_context") or "").strip()
        chat_id_val = data.get("chat_id")
        try:
            chat_id = int(chat_id_val)
        except Exception:
            chat_id = _stable_chat_id(sid)
        use_rag = bool(data.get("use_rag", True))
        temp = data.get("temperature")
        if temp is not None:
            try:
                temp = float(temp)
            except Exception:
                temp = None

        res: Dict[str, Any]
        live_enabled = _env_bool("ESTER_WEB_USE_ARBITRAGE", True)
        live_text = ""
        live_provider = ""
        if live_enabled and message:
            live_text, live_provider = _call_main_live_arbitrage(
                text=message,
                sid=sid,
                user_id=user_id,
                user_name=user_name,
                chat_id=chat_id,
                address_as=address_as,
                tone_context=tone_context,
                file_context=file_context,
            )

        if live_text:
            _save_clean_memory(message, live_text)
            res = {
                "ok": True,
                "sid": sid,
                "mode": (mode or "hive"),
                "provider": live_provider or "hivemind",
                "engine": "hivemind",
                "reply": live_text,
                "answer": live_text,
                "response": live_text,
            }
        else:
            res = handle_message(message, history=history, engine=engine, temperature=temp)
            if res.get("ok"):
                reply_text = str(res.get("reply") or "").strip()
                if reply_text:
                    res.setdefault("answer", reply_text)
                    res.setdefault("response", reply_text)
                res.setdefault("sid", sid)
                res.setdefault("mode", mode or "legacy")

        if use_rag and res.get("ok"):
            try:
                from modules.rag.retrieval_router import retrieve as _rr_retrieve  # type: ignore
                rr = _rr_retrieve(message)
                res["provenance"] = rr.get("provenance") or []
                res["router_stats"] = rr.get("stats") or {}
            except Exception:
                pass
        if not res.get("ok"):
            return jsonify(res), 400
        return jsonify(res)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


def register(app):
    app.register_blueprint(bp)


# ----------------------------- Telegram async wrapper -----------------------------
async def handle_message_telegram(update, context):
    """
    Async wrapper dlya Telegram.
    Izvlekaet tekst iz update i vyzyvaet handle_message.
    """
    from telegram import Update
    from telegram.ext import ContextTypes
    import asyncio

    msg = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if not msg:
        return

    text = getattr(msg, "text", None) or ""
    text = (text or "").strip()
    if not text:
        return

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, lambda: handle_message(text))
    except Exception as e:
        logging.warning(f"[chat_api] telegram wrapper error: {e}")
        return

    reply = ""
    if isinstance(result, dict):
        reply = str(result.get("reply") or result.get("text") or "").strip()
    else:
        reply = str(result or "").strip()

    if reply and msg:
        try:
            await msg.reply_text(reply)
        except Exception as e:
            logging.warning(f"[chat_api] reply failed: {e}")
