# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class ResearchAgent:
    """
    Mok-agent issledovaniy.
    search(query) -> spisok rezultatov [{title, snippet}]
    V realnoy realizatsii mog by khodit v veb/vektorku; zdes — prostaya zaglushka na dannye zaprosa.
    """

    def search(self, query: str) -> List[Dict[str, str]]:
        q = (query or "").strip()
        if not q:
            return []
        
        # Ispravlen sintaksis spiska i kodirovka strok
        return [
            {
                "title": f"Rezultat po zaprosu: {q}",
                "snippet": f"Kratkaya vyzhimka dlya «{q}».",
            },
            {
                "title": f"Metody i podkhody ({q})",
                "snippet": "Spisok istochnikov i podkhodov.",
            },
            {
                "title": f"FAQ: {q}", 
                "snippet": "Chastye voprosy i otvety."
            },
        ]