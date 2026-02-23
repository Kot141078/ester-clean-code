# -*- coding: utf-8 -*-
import os
import json
import time
import logging
from typing import List, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Nastroyki pod 2x RTX 5060 Ti 16GB
MAX_SESSION_TOKENS = 16000  # Limit konteksta
SESSION_FILE = os.path.join("state", "active_session.json")

class SessionGuardian:
    """
    Strazh sessiy Ester: monitoring byudzheta tokenov i umnaya summarizatsiya.
    """
    def __init__(self, core=None):
        self.core = core
        self.session_id = f"sess_{int(time.time())}"
        self._ensure_state()

    def _ensure_state(self):
        os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
        if not os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    async def auto_summarize(self, context: List[Dict]) -> str:
        if len(context) < 10:
            return ""
        to_summarize = context[1:-5]
        summary = f"[Summatsiya: Ester obrabotala {len(to_summarize)} soobscheniy v fone]"
        return summary

    def protect(self, context_list: List[Dict]) -> List[Dict]:
        total_tokens = sum(self.estimate_tokens(m.get("content", "")) for m in context_list)
        
        # Esli vlezaem v pamyat videokart — ne trogaem
        if total_tokens < MAX_SESSION_TOKENS:
            return context_list

        logging.info(f"[Guardian] Perepolnenie ({total_tokens} > {MAX_SESSION_TOKENS}). Szhimayu...")
        
        system_msg = context_list[0] if context_list[0]["role"] == "system" else None
        # Ostavlyaem tolko poslednie 10 replik
        fresh_context = context_list[-10:]
        
        if system_msg and system_msg not in fresh_context:
            return [system_msg] + fresh_context
        return fresh_context

    def smoketest(self):
        """Test: generiruem 'tyazhelyy' musor, chtoby probit limit v 16000 tokenov."""
        # Generiruem ochen dlinnoe soobschenie (okolo 1000 tokenov kazhdoe)
        heavy_msg = "test " * 1000 
        # Sozdaem 50 takikh soobscheniy (50 * 1000 = 50 000 tokenov > 16 000)
        test_data = [{"role": "user", "content": heavy_msg}] * 50
        
        result = self.protect(test_data)
        
        # Esli szhatie srabotalo, ostanetsya okolo 10-11 soobscheniy
        if len(result) <= 20:
             return "OK: Szhatie rabotaet (Heavy Load Test Passed)."
        return f"FAILED: Szhatie ne srabotalo, ostalos {len(result)} soobscheniy."