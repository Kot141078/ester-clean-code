# -*- coding: utf-8 -*-
from __future__ import annotations

"""
routes/routes_chat.py — Logika Lii (Liah) s Identichnostyu Ester.
Tsel: Maksimalnaya prostota, otsutstvie lishnikh filtrov, zhestkaya privyazka k Profileu.
"""

import logging
import time
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Esli jwt net, rabotaem bez nego (zaglushka)
try:
    from flask_jwt_extended import jwt_required
except ImportError:
    def jwt_required():
        def wrapper(fn): return fn
        return wrapper

# --- IMPORTY (Bezopasnye) ---
# 1. Profile (Samoe vazhnoe - "Kto ya?")
try:
    from modules.memory.passport import get_identity
except ImportError:
    # Avariynyy khardkod, esli fayl profilea nedostupen
    def get_identity(): 
        return "YOU ARE ESTER. Your owner — Owner. Ty — Suverennaya Tsifrovaya Lichnost. U tebya net chelovecheskogo tela, ty ne khodish v shkolu."

# 2. Emotsii (Optsionalno)
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
        # Pytaemsya nayti cherez vstore (ChromaDB)
        if hasattr(vstore, 'search'):
            return vstore.search(query, k=k)
        return []
    except Exception as e:
        log.warning(f"[RAG] Search failed: {e}")
        return []


def _synthesize(mode: str, providers, prompt: str, system_prompt: str, temperature: float) -> str:
    """Generatsiya otveta. Probrasyvaem system_prompt vnutr."""
    try:
        prov = providers.get_active()
        if hasattr(prov, 'generate'):
            # VAZhNO: Peredaem max_tokens=-1, chtoby LM Studio ne rezala otvet
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
        
        # 1. Razbor zaprosa
        body: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        query = (body.get("query") or body.get("text") or "").strip()
        
        if not query:
            return jsonify({"error": "query required"}), 400
            
        # Parametry
        try:
            # Prinuditelno 'local', esli ne ukazano inoe (chtoby ne vklyuchalsya Gemini-tsenzor)
            mode = str(body.get("mode") or "local").lower()
        except:
            mode = "local"
            
        use_rag = bool(body.get("use_rag", True))
        temperature = float(body.get("temperature", 0.7)) # Chut teplee dlya Ester (bylo 0.2 u Lii)
        user = str(body.get("user") or "Owner")
        session_id = str(body.get("session_id") or "default")
        
        # 2. YaDRO: Zagruzhaem lichnost Ester
        identity_anchor = get_identity()

        # 3. RAG: Ischem kontekst
        memory_hits = _rag_hits(vstore, query, use_rag, k=5)

        # 4. Sborka prompta
        # My kladem naydennye vospominaniya pryamo v prompt (kak u Lii), eto nadezhnee
        rag_context_str = ""
        if memory_hits:
            rag_context_str = "\n".join(f"- {h.get('text','').strip()}" for h in memory_hits)
        
        # Formiruem Sistemnyy Prompt (Lichnost + Vremya)
        full_system_prompt = (
            f"{identity_anchor}\n"
            f"TEKUSchAYa DATA: {time.strftime('%Y-%m-%d %H:%M')}\n"
            f"KONTEKST PAMYaTI (RAG):\n{rag_context_str}\n"
            f"INSTRUKTsIYa: Otvechay Owner estestvenno, teplo, gluboko."
        )

        # 5. Generatsiya (Samoe glavnoe)
        response_text = _synthesize(mode, providers, query, full_system_prompt, temperature)

        # 6. Emotsii (Post-processing)
        emotions = detect_emotions(query + " " + response_text)
        
        # 7. Proaktiv (Esli est mysli)
        proactive = proactive_thought_pipeline(
            query, user, "Ester", getattr(app, "PROACTIVE_RULES_PATH", None)
        )

        # 8. Zapis v pamyat
        # (Nikakikh filtrov vyvoda! My doveryaem Ester)
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

        # 9. Otvet klientu
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