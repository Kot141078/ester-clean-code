# engines/serpapi_bridge.py
# Provayder B: SerpAPI (Google Web)
import os, requests
from typing import Dict, Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def serp_search(query: str, limit: int = 5, lang: Optional[str] = None, timeout_s: int = 10) -> Dict[str, Any]:
    key = os.getenv("SERPAPI_KEY")
    if not key:
        return {"ok": False, "items": [], "provider": "serpapi", "error": "missing_serpapi_key"}

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": query,
        "api_key": key,
        "num": max(1, min(limit, 10)),
        # hl: yazyk interfeysa, gl: geo
    }
    if lang:
        params["hl"] = lang

    try:
        r = requests.get(url, params=params, timeout=timeout_s)
    except Exception as e:
        return {"ok": False, "items": [], "provider": "serpapi", "error": f"request_error:{type(e).__name__}:{e}"}

    if r.status_code != 200:
        return {"ok": False, "items": [], "provider": "serpapi", "error": f"http_{r.status_code}"}

    data = r.json()
    items = []
    for it in data.get("organic_results", []) or []:
        link = it.get("link") or it.get("url")
        if not link:
            continue
        items.append({
            "title": it.get("title", ""),
            "url": link,
            "snippet": it.get("snippet", "") or it.get("snippet_highlighted_words", ""),
        })
    return {"ok": bool(items), "items": items, "provider": "serpapi", "error": None if items else "no_results"}