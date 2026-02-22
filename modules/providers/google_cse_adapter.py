import os
import requests
import logging
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)

def search(query: str, limit: int = 5, **kwargs) -> dict:
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    
    if not api_key or not cse_id:
        log.error("Google Config Missing: Check .env for GOOGLE_API_KEY/CSE_ID")
        return {"ok": False, "error": "config_missing", "items": []}

    try:
        # Ispolzuem Custom Search JSON API
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"key": api_key, "cx": cse_id, "q": query, "num": limit}
        
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code != 200:
            log.error(f"Google API Error {resp.status_code}: {resp.text}")
            return {"ok": False, "error": f"http_{resp.status_code}", "items": []}
            
        data = resp.json()
        items = []
        for item in data.get("items", []):
            items.append({
                "title": item.get("title"),
                "url": item.get("link"),
                "snippet": item.get("snippet", "")
            })
            
        return {"ok": True, "items": items, "provider": "google_real"}
        
    except Exception as e:
        log.error(f"Google Adapter Exception: {e}")
        return {"ok": False, "error": str(e), "items": []}