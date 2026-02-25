import os
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# Trying to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

print(f"\n--- 1. CONFIG CHECK ---")
print(f"CLOSED_BOX: {os.getenv('CLOSED_BOX', 'Unknown')}")
print(f"WEB_ALLOW_FETCH: {os.getenv('WEB_ALLOW_FETCH', 'Unknown')}")

print(f"\n--- 2. DRIVER CHECK ---")
try:
    from duckduckgo_search import DDGS
    print("✅ Library 'duckduckgo_search' imported successfully.")
    
    print(f"\n--- 3. PING GOOGLE (Connectivity) ---")
    import requests
    try:
        r = requests.get("https://www.google.com", timeout=5)
        print(f"✅ Google Reachable (Status: {r.status_code})")
    except Exception as e:
        print(f"❌ Google Unreachable: {e}")

    print(f"\n--- 4. SEARCH TEST (Query: 'current bitcoin price') ---")
    try:
        with DDGS() as ddgs:
            # Trying a simple text search
            results = list(ddgs.text("current bitcoin price", max_results=1))
            if results:
                print(f"✅ SUCCESS! Found result: {results[0].get('title', 'No Title')}")
                print(f"   Snippet: {results[0].get('body', '')[:60]}...")
            else:
                print("❌ FAILURE: Driver returned empty list (Possible IP ban or region block).")
    except Exception as e:
        print(f"❌ EXECUTION ERROR: {e}")

except ImportError:
    print("❌ CRITICAL: 'duckduckgo_search' library not found in Python environment.")
except Exception as e:
    print(f"❌ ERROR: {e}")