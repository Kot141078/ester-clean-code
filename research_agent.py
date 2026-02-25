# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class ResearchAgent:
    """Mok-agent issledovaniy.
    search(query) -> spisok rezultatov [{title, snippet}]
    V realnoy realizatsii mog by khodit v web/vektorku; zdes - prostaya zaglushka na dannye zaprosa."""

    def search(self, query: str) -> List[Dict[str, str]]:
        q = (query or "").strip()
        if not q:
            return []
        
        # Ispravlen sintaksis spiska i kodirovka strok
        return [
            {
                "title": f"Search result: ZZF0Z",
                "snippet": f"A short summary for “ZZF0Z”.",
            },
            {
                "title": f"Metody i podkhody ({q})",
                "snippet": "List of sources and approaches.",
            },
            {
                "title": f"FAQ: {q}", 
                "snippet": "Frequently asked questions and answers."
            },
        ]