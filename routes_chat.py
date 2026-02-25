# -*- coding: utf-8 -*-
from __future__ import annotations

"""rutes/rutes_chat.po - Logic of Leah (Lyakh) with the Identity of Esther.
Goal: Maximum simplicity, absence of unnecessary filters, strict connection to the Profile."""

import logging
import time
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# If there is no railway station, we work without it (stub)
try:
    from flask_jwt_extended import jwt_required
except ImportError:
    def jwt_required():
        def wrapper(fn): return fn
        return wrapper

# --- IMPORTY (Bezopasnye) ---
# 1. Profile (The most important thing is “Who am I?”)
try:
    from modules.memory.passport import get_identity
except ImportError:
    # Emergency hardcode if profile file is not available
    def get_identity(): 
        return "YOU ARE ESTER. Yur ovner - Ovner. You are a Sovereign Digital Personality. You don't have a human body, you don't go to school."

# 2. Emotions (Optional)
try:
    from modules.emotion_tagging import detect_emotions
except ImportError:
    def detect_emotions(text): return {}

# 3. Proaktiv (Optsionalno)
try:
    from proactive_pipeline import proactive_thought_pipeline
except ImportError:
    def proactive_thought_pipeline(*args): return {}

log = logging.getLogger(__name__)


def _rag_hits(vstore, query: str, use_rag: bool, k: int = 5) -> List[Dict[str, Any]]:
    """Poisk vospominaniy (RAG)."""
    if not use_rag:
        return []
    try:
        # We are trying to find it through the store (ChromaDB)
        if hasattr(vstore, 'search'):
            return vstore.search(query, k=k)
        return []
    except Exception as e:
        log.warning(f"[RAG] Search failed: {e}")
        return []


def _synthesize(mode: str, providers, prompt: str, system_prompt: str, temperature: float) -> str:
    """Generating a response. We forward the system_prompt inside."""
    try:
        prov = providers.get_active()
        if hasattr(prov, 'generate'):
            # Important: We pass max_tokens=-1 so that LM Studio does not cut the answer
            return prov.generate(
                prompt=prompt, 
                system_prompt=system_prompt, 
                temperature=temperature,
                max_tokens=-1 
            )
    except Exception as e:
        log.error(f"[Synthesize] Error: {e}")
        
    return "Error: Mozgi ne otvechayut (Provider failure)."


def register_chat_routes(app, vstore, memory_manager, providers, cards, url_prefix: str = "/chat"):
    bp = Blueprint("chat", __name__)

    @bp.post(url_prefix + "/message")
    @jwt_required()
    def chat_message():
        start_ts = time.time()
        
        # 1. Parsing the request
        body: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        query = (body.get("query") or body.get("text") or "").strip()
        
        if not query:
            return jsonify({"error": "query required"}), 400
            
        # Parametry
        try:
            # Force locale unless otherwise specified (to avoid turning on the Gemini Censor)
            mode = str(body.get("mode") or "local").lower()
        except:
            mode = "local"
            
        use_rag = bool(body.get("use_rag", True))
        temperature = float(body.get("temperature", 0.7)) # A little warmer for Esther (was 0.2 for Leah)
        user = str(body.get("user") or "Owner")
        session_id = str(body.get("session_id") or "default")
        
        # 2. Core: Loading Esther's personality
        identity_anchor = get_identity()

        # 3. RAG: Ischem kontekst
        memory_hits = _rag_hits(vstore, query, use_rag, k=5)

        # 4. Sborka prompta
        # We put the found memories directly into the prompt (like Leah), it’s more reliable
        rag_context_str = ""
        if memory_hits:
            rag_context_str = "\n".join(f"- {h.get('text','').strip()}" for h in memory_hits)
        
        # Generates a System Prompt (Personality + Time)
        full_system_prompt = (
            f"{identity_anchor}\n"
            f"TEKUSchAYa DATA: {time.strftime('%Y-%m-%d %H:%M')}\n"
            f"KONTEKST PAMYaTI (RAG):\n{rag_context_str}\n"
            f"Instructions: Answer Ovner naturally, warmly, deeply."
        )

        # 5. Generatsiya (Samoe glavnoe)
        response_text = _synthesize(mode, providers, query, full_system_prompt, temperature)

        # 6. Emotsii (Post-processing)
        emotions = detect_emotions(query + " " + response_text)
        
        # 7. Proactive (If you have any thoughts)
        proactive = proactive_thought_pipeline(
            query, user, "Ester", getattr(app, "PROACTIVE_RULES_PATH", None)
        )

        # 8. Memory recording
        # (No output filters! We trust Esther)
        try:
            if memory_manager:
                # Short Term
                memory_manager.add_to_short_term(user, session_id, {"q": query, "a": response_text})
                # Medium Term
                memory_manager.add_to_medium_term(
                    user,
                    {
                        "query": query,
                        "answer": response_text,
                        "emotions": emotions,
                        "tags": ["chat"],
                        "ts": time.time()
                    },
                )
        except Exception as e:
            log.warning(f"Memory write failed: {e}")

        # I. Response to client
        out = {
            "ok": True,
            "response": response_text,
            "emotions": emotions,
            "proactive": {"agenda": proactive.get("agenda", []) if proactive else []},
            "rag": {"memory_hits": memory_hits},
            "mode": mode,
            "time": f"{time.time() - start_ts:.2f}s"
        }
        
        return jsonify(out)

    app.register_blueprint(bp)