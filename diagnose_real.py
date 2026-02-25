from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import sys, os
try:
    from dotenv import load_dotenv
    load_dotenv() # Loading keys from .env
    print("[INFO] .env zagruzhen")
except ImportError:
    print("YuVARNsch pothon-dotenv is not installed, keys may not be available")

try:
    from modules.net import net_bridge_adapter
    print("[OK] Import net_bridge_adapter proshel")
    
    key = os.getenv("GOOGLE_API_KEY")
    print(f"[CHECK] GOOGLE_API_KEY nayden? {bool(key)}")
    if key:
        print(f"YuCHETSKsch First 5 characters of the key: ZZF0Z...")
    
    print("--- Probuem poisk ---")
    res = net_bridge_adapter.search("kurs dollara")
    print(f"[RESULT] {res}")
    
except Exception as e:
    print(f"yuFAILsch Error: ZZF0Z")