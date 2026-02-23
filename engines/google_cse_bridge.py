# engines/google_cse_bridge.py
# Provayder A: Google Custom Search JSON API
import os, json, requests
from typing import Dict, Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def gcs_search(query: str, limit: int = 5, lang: Optional[str] = None, timeout_s: int = 10) -> Dict[str, Any]:
    key = os.getenv("GOOGLE_API_KEY")
    cx  = os.getenv("GOOGLE_CSE_ID")
    if not key or not cx:
        return {"ok": False, "items": [], "provider": "google_cse", "error": "missing_google_keys"}

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": key,
        "cx": cx,
        "q": query,
        "num": max(1, min(limit, 10)),
    }
    if lang:
        # Google CSE: lr=lang_ru, ili lr=lang_en
        params["lr"] = f"lang_{lang}" if len(lang) == 2 else lang

    try:
        r = requests.get(url, params=params, timeout=timeout_s)
    except Exception as e:
        return {"ok": False, "items": [], "provider": "google_cse", "error": f"request_error:{type(e).__name__}:{e}"}

    if r.status_code != 200:
        return {"ok": False, "items": [], "provider": "google_cse", "error": f"http_{r.status_code}"}

    data = r.json()
    items = []
    for it in data.get("items", []) or []:
        items.append({
            "title": it.get("title", ""),
            "url": it.get("link", ""),
            "snippet": it.get("snippet", ""),
        })
    return {"ok": bool(items), "items": items, "provider": "google_cse", "error": None if items else "no_results"}