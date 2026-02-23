import requests
import json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

url = "http://127.0.0.1:8090/ester/net/search"
# Zapros, na kotorom ona "posypalas"
query = "RTX 5090 32 gb astral lc" 

print(f"--- TEST POISKA: '{query}' ---")
try:
    resp = requests.post(url, json={"q": query, "src": "debug_script"}, timeout=30)
    print(f"Status Code: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("results", []) or data.get("items", [])
        print(f"Naydeno rezultatov: {len(items)}")
        for i, item in enumerate(items[:3]):
            print(f"[{i+1}] {item.get('title')} ({item.get('link')})")
            print(f"    {item.get('snippet')[:100]}...")
    else:
        print(f"Oshibka servera: {resp.text}")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")