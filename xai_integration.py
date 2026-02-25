# -*- coding: utf-8 -*-
"""xai_integration.py - Integratesiya xAI/Grok + OpenAI, Gemini (Google AI), Claude.
Rezhim: vybiraet provaydera po emotsii/nastroeniyu i delaet fallback na lokalnyy LLM."""
from __future__ import annotations

import json
import os
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from emotional_engine import EmotionalAnalyzer
from memory_manager import MemoryManager

try:
    import chromadb  # type: ignore
except Exception:
    chromadb = None  # type: ignore

try:
    from cryptography.fernet import Fernet
except Exception:
    Fernet = None  # type: ignore

PROVIDERS: Dict[str, Dict[str, str]] = {
    "xai": {
        "url": "https://api.x.ai/v1/chat/completions",
        "key": os.getenv("XAI_API_KEY", ""),
        "model": os.getenv("XAI_MODEL", "grok-4"),
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "key": os.getenv("OPENAI_API_KEY", ""),
        "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
        "key": os.getenv("GEMINI_API_KEY", ""),
        "model": os.getenv("GEMINI_MODEL", "gemini-pro"),
    },
    "claude": {
        "url": "https://api.anthropic.com/v1/messages",
        "key": os.getenv("CLAUDE_API_KEY", ""),
        "model": os.getenv("CLAUDE_MODEL", "claude-3-opus-20240229"),
    },
}


class XAIIntegrator:
    def __init__(self) -> None:
        self.emotion_analyzer = EmotionalAnalyzer()
        self.memory_manager = self._build_mm()

        # Chroma memory (optional)
        if chromadb is not None:
            try:
                self.chroma_client = chromadb.Client()
                self.collection = self.chroma_client.get_or_create_collection("ester_xai_memory")
            except Exception:
                self.chroma_client = None
                self.collection = None
        else:
            self.chroma_client = None
            self.collection = None

        # Encryption (optional)
        self.cipher = None
        if Fernet is not None:
            key = os.getenv("ENCRYPTION_KEY", "").strip()
            if not key:
                key = Fernet.generate_key().decode("utf-8")
            self.cipher = Fernet(key.encode("utf-8"))

        self.state_dir = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
        self.vstore_dir = self.state_dir / "vstore"
        self.vstore_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.vstore_dir / "ester_xai_log.json"

    def _build_mm(self) -> MemoryManager:
        try:
            from cards_memory import CardsMemory  # type: ignore
            from structured_memory import StructuredMemory  # type: ignore
            from vector_store import VectorStore  # type: ignore
        except Exception:
            class _MMStub:  # minimal fallback
                def add_to_long_term(self, text: str) -> None:
                    return None
            return _MMStub()  # type: ignore[return-value]

        persist_dir = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
        os.makedirs(persist_dir, exist_ok=True)
        vstore = VectorStore(
            collection_name=os.getenv("COLLECTION_NAME", "ester_store"),
            persist_dir=persist_dir,
            use_embeddings=bool(int(os.getenv("USE_EMBEDDINGS", "0"))),
        )
        structured = StructuredMemory(os.path.join(persist_dir, "structured_mem", "store.json"))  # type: ignore
        cards = CardsMemory(os.path.join(persist_dir, "ester_cards.json"))  # type: ignore
        return MemoryManager(vstore, structured, cards)  # type: ignore

    def _encrypt(self, text: str) -> str:
        if self.cipher is None:
            return text
        try:
            return self.cipher.encrypt(text.encode("utf-8")).decode("utf-8")
        except Exception:
            return text

    def _call_provider(self, provider: str, prompt: str) -> str:
        prov = PROVIDERS.get(provider) or {}
        if not prov.get("key"):
            return ""

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        payload: Dict[str, Any] = {}

        if provider in ("xai", "openai"):
            headers["Authorization"] = f"Bearer {prov['key']}"
            payload = {
                "model": prov.get("model"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            }
        elif provider == "gemini":
            headers["x-goog-api-key"] = prov.get("key", "")
            payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        elif provider == "claude":
            headers["x-api-key"] = prov.get("key", "")
            headers["anthropic-version"] = "2023-06-01"
            payload = {
                "model": prov.get("model"),
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}],
            }

        r = requests.post(prov.get("url", ""), headers=headers, json=payload, timeout=40)
        r.raise_for_status()
        j = r.json()

        if provider in ("xai", "openai"):
            return (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        if provider == "gemini":
            return ((j.get("candidates") or [{}])[0].get("content") or {}).get("parts", [{}])[0].get("text") or ""
        if provider == "claude":
            return (j.get("content") or [{}])[0].get("text") or ""
        return ""

    def local_llm_synth(self, user_input: str, user_emotion: Dict[str, Any]) -> str:
        try:
            base = os.getenv("LMSTUDIO_BASE_URL", os.getenv("LLM_API_BASE", "http://127.0.0.1:1234/v1")).rstrip("/")
            model = os.getenv("LMSTUDIO_MODEL", os.getenv("LLM_MODEL", "local-model"))
            url = f"{base}/chat/completions"
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": f"Synthesize: {user_input}. Emotion: {user_emotion.get('emotion', 'neutral')}."}
                ],
                "temperature": 0.7,
                "max_tokens": 600,
            }
            r = requests.post(url, json=payload, timeout=40)
            r.raise_for_status()
            j = r.json()
            return (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        except Exception:
            return "Local synth: Empathetic response."

    def synthesize_with_xai(
        self,
        user_input: str,
        local_responses: Optional[List[str]] = None,
        user_emotion: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
    ) -> str:
        local_responses = local_responses or []
        if not user_emotion:
            user_emotion = self.emotion_analyzer.analyze_emotion(user_input)

        if provider == "all":
            synth_outputs = self.group_synth(user_input, local_responses, user_emotion)
            synth_output = self.judge_group(synth_outputs, user_input)
            selected_provider = "group"
        else:
            if not provider:
                emotion = user_emotion.get("emotion")
                if emotion == "positive":
                    provider = "openai"
                elif emotion == "negative":
                    provider = "claude"
                else:
                    provider = random.choice(list(PROVIDERS.keys()))

            prompt = (
                f"Synthesize this query: '{user_input}'. "
                f"Local responses: {local_responses}. "
                f"Emotion: {user_emotion.get('emotion')}. "
                "Provide empathetic, proactive response."
            )

            synth_output = ""
            try:
                synth_output = self._call_provider(provider, prompt)  # type: ignore[arg-type]
            except Exception:
                synth_output = ""

            if not synth_output:
                synth_output = self.local_llm_synth(user_input, user_emotion)

            selected_provider = provider

        final_response = f"Synthesis from ZZF0Z: ZZF1ZZ. I remember your ZZF2ZZ, how can I help?"

        encrypted_data = self._encrypt(f"{user_input}|{synth_output}")
        if self.collection is not None:
            try:
                self.collection.add(documents=[encrypted_data], metadatas=[user_emotion])
            except Exception:
                pass

        try:
            if hasattr(self.memory_manager, "add_to_long_term"):
                self.memory_manager.add_to_long_term(encrypted_data)
        except Exception:
            pass

        proactive = self.emotion_analyzer.proactive_response(user_emotion)
        self.p2p_sync(encrypted_data + "|" + proactive)
        self.log_choice(selected_provider, user_emotion)

        return final_response + " " + proactive

    def group_synth(self, user_input: str, local_responses: List[str], user_emotion: Dict[str, Any]) -> Dict[str, str]:
        def call_provider(prov_name: str):
            return prov_name, self.synthesize_with_xai(user_input, local_responses, user_emotion, provider=prov_name)

        with ThreadPoolExecutor() as executor:
            results = executor.map(call_provider, PROVIDERS.keys())
        return dict(results)

    def judge_group(self, synth_outputs: Dict[str, str], user_input: str) -> str:
        prompt = f"Judge these synths for query '{user_input}': {synth_outputs}. Choose the best empathetic one."
        prov = PROVIDERS["xai"]
        if prov.get("key"):
            try:
                headers = {"Authorization": f"Bearer {prov['key']}", "Content-Type": "application/json"}
                data = {"model": prov.get("model"), "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
                response = requests.post(prov.get("url", ""), headers=headers, json=data, timeout=40)
                response.raise_for_status()
                return response.json().get("choices", [{}])[0].get("message", {}).get("content") or ""
            except Exception:
                pass
        return list(synth_outputs.values())[0] if synth_outputs else ""

    def background_process(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        synth_response = self.synthesize_with_xai(content)
        self.p2p_sync(synth_response)
        return synth_response

    def p2p_sync(self, data: str) -> None:
        print(f"P2P sync: Broadcasting {len(data)} bytes to peers.")

    def log_choice(self, provider: str, user_emotion: Dict[str, Any]) -> None:
        from datetime import datetime
        log_entry = {"ts": datetime.utcnow().isoformat(), "provider": provider, "emotion": user_emotion.get("emotion")}
        try:
            if self.log_file.exists():
                logs = json.loads(self.log_file.read_text(encoding="utf-8"))
                logs.append(log_entry)
            else:
                logs = [log_entry]
            self.log_file.write_text(json.dumps(logs, indent=2, ensure_ascii=False))
        except Exception:
            pass


if __name__ == "__main__":
    integrator = XAIIntegrator()
    query = "Rasskazhi o Ilone i AI."
    print(integrator.synthesize_with_xai(query))
# c=a+b
