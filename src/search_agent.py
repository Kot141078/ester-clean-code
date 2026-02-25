# -*- coding: utf-8 -*-
"""Asynchronous search agent (Google + wrapper)."""
import asyncio
from typing import Any, Dict, List, Optional

from src.search import google_search
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class SearchAgent:
    async def search(
        self, query: str, num_results: int = 3, date_restrict: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        # Simulate asynchronous search (takes it into the thread so as not to block the event loop)
        return await asyncio.to_thread(google_search, query)
