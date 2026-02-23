from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import sys, os
try:
    from dotenv import load_dotenv
    load_dotenv() # Zagruzhaem klyuchi iz .env
    print("[INFO] .env zagruzhen")
except ImportError:
    print("[WARN] python-dotenv ne ustanovlen, klyuchi mogut byt nedostupny")

try:
    from modules.net import net_bridge_adapter
    print("[OK] Import net_bridge_adapter proshel")
    
    key = os.getenv("GOOGLE_API_KEY")
    print(f"[CHECK] GOOGLE_API_KEY nayden? {bool(key)}")
    if key:
        print(f"[CHECK] Pervye 5 simvolov klyucha: {key[:5]}...")
    
    print("--- Probuem poisk ---")
    res = net_bridge_adapter.search("kurs dollara")
    print(f"[RESULT] {res}")
    
except Exception as e:
    print(f"[FAIL] Oshibka: {e}")