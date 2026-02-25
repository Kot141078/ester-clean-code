import logging
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
log = logging.getLogger(__name__)

# Import the provider (which we updated above)
try:
    from modules.providers import google_cse_adapter
except ImportError:
    google_cse_adapter = None

def get_config(): return {"provider": "google_cse"}

def search(query: str, limit: int = 5, **kwargs) -> Dict[str, Any]:
    if not google_cse_adapter:
        return {"ok": False, "error": "no_adapter", "items": []}
    
    log.info(f"NET_BRIDGE: Searching for {query}")
    return google_cse_adapter.search(query=query, limit=limit)