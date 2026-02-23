#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ester Net Diagnostics (v0.2 - Fixed)
Proveryaet:
- ENV peremennye
- HTTP dostup k Google
- [FIX] Aktualnyy modul modules.net.net_bridge_adapter (vmesto starogo web_search)
"""

import os
import sys
import json
import socket
from pathlib import Path
from dotenv import load_dotenv
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Nakhodim koren proekta
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

try:
    import requests
except ImportError:
    requests = None

def safe_env(name: str) -> str:
    val = os.getenv(name)
    if val is None: return "<NOT SET>"
    if len(val) <= 6: return f"<SET len={len(val)}>"
    return f"<SET len={len(val)}, head={val[:3]}***tail={val[-3:]}>"

def collect_env() -> dict:
    keys = [
        "SPREAD_AB", "SPREAD_GUARD_MODE", "SPREAD_ALLOW_NETS", "SPREAD_ALLOW_HOSTS", 
        "SPREAD_DENY", "SELF_LOG", "ESTER_NET_AUTOBRIDGE", "ESTER_NET_MODE", 
        "ESTER_NET_DEBUG", "GOOGLE_API_KEY", "GOOGLE_CSE_ID", "OPENAI_API_KEY", 
        "GEMINI_API_KEY"
    ]
    return {k: safe_env(k) for k in keys}

def test_dns_and_http() -> dict:
    out = {}
    # 1. DNS
    try:
        ip = socket.gethostbyname("google.com")
        out["google_dns"] = {"ok": True, "ip": ip}
    except Exception as e:
        out["google_dns"] = {"ok": False, "error": str(e)}
    
    # 2. HTTP
    if requests:
        try:
            r = requests.get("https://www.google.com", timeout=5)
            out["google_http"] = {"ok": True, "status_code": r.status_code, "len": len(r.text)}
        except Exception as e:
            out["google_http"] = {"ok": False, "error": str(e)}
    else:
        out["google_http"] = {"ok": False, "error": "requests library missing"}
        
    return out

def test_net_bridge() -> dict:
    """
    [FIX] Proveryaem modules.net.net_bridge_adapter
    """
    out = {"import_ok": False, "search_ok": False}
    try:
        from modules.net import net_bridge_adapter
        out["import_ok"] = True
        
        # Probuem realnyy poisk
        if hasattr(net_bridge_adapter, "search"):
            # Testovyy zapros
            try:
                res = net_bridge_adapter.search("test ping", limit=1)
                if res.get("ok"):
                    out["search_ok"] = True
                    out["result_sample"] = str(res["items"])[:100] + "..."
                else:
                    out["search_ok"] = False
                    out["error_from_adapter"] = res.get("error")
            except Exception as e:
                out["search_error"] = str(e)
        else:
            out["error"] = "Module has no .search() method"
            
    except ImportError as e:
        out["error"] = f"Import failed: {e}"
    except Exception as e:
        out["error"] = f"Unexpected: {e}"
        
    return out

def main():
    print(f"=== Ester Net Diagnostics (v0.2) ===")
    print(f"ROOT: {ROOT}")
    
    print("\n[1] Environment snapshot")
    print(json.dumps(collect_env(), indent=2, ensure_ascii=False))
    
    print("\n[2] DNS / HTTP sanity")
    print(json.dumps(test_dns_and_http(), indent=2, ensure_ascii=False))
    
    print("\n[3] modules.net.net_bridge_adapter sanity")
    print(json.dumps(test_net_bridge(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()