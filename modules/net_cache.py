# -*- coding: utf-8 -*-
"""modules/net_cache.py - Short-term memory for network requests.
Reduces noise and saves credits."""
import json
import os
import hashlib
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

CACHE_FILE = "data/net_cache.json"
TTL_SECONDS = 86400  # 24 hours

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def get_cached(key_prefix, query):
    """Returns cached data if valid."""
    cache = load_cache()
    h = hashlib.md5(query.encode()).hexdigest()
    key = f"{key_prefix}:{h}"
    
    if key in cache:
        entry = cache[key]
        if time.time() - entry["ts"] < TTL_SECONDS:
            return entry["data"]
    return None

def set_cached(key_prefix, query, data):
    """Saves data to cache."""
    cache = load_cache()
    h = hashlib.md5(query.encode()).hexdigest()
    key = f"{key_prefix}:{h}"
    
    cache[key] = {
        "ts": time.time(),
        "data": data,
        "query": query
    }
    save_cache(cache)