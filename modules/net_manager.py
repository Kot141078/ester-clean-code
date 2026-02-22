# -*- coding: utf-8 -*-
"""
modules/net_manager.py - The Brain's interface to the Web.
Routes requests to cache or bridge.
"""
from modules import net_bridge, net_cache, html_extract
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def search_internet(query, force=False):
    """
    Orchestrates search:
    1. Check Cache
    2. If miss, call Bridge
    3. Save to Cache
    """
    if not force:
        cached = net_cache.get_cached("search", query)
        if cached:
            print(f"[NetManager] 🟢 Cache Hit: {query}")
            return cached
            
    print(f"[NetManager] rџџ  Cache Miss. Calling Bridge...")
    result = net_bridge.search({"q": query})
    
    if result.get("ok"):
        net_cache.set_cached("search", query, result)
        
    return result

def ingest_url(url):
    """
    Fetches a specific URL, extracts text.
    Does NOT auto-save to memory (that's the Will's job).
    """
    print(f"[NetManager] 📥 Ingesting: {url}")
    return html_extract.fetch_and_clean(url)