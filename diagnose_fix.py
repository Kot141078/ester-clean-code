import sys
import os
import logging
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Nastroyka logirovaniya v konsol
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger("DIAG")

print("=== 1. PROVERKA PUTEY MODULEY ===")
try:
    from modules import chat_api
    print(f" [OK] chat_api zagruzhen iz: {chat_api.__file__}")
except ImportError as e:
    print(f" [FAIL] chat_api ne nayden: {e}")

try:
    from modules import web_search
    print(f" [OK] web_search zagruzhen iz: {web_search.__file__}")
    if hasattr(web_search, "search_web"):
        print("      -> Metod .search_web() nayden.")
    else:
        print("      -> [ALARM] Metod .search_web() OTSUTSTVUET!")
except ImportError:
    print(" [INFO] modules.web_search ne nayden")

try:
    from modules import net_bridge
    print(f" [OK] net_bridge zagruzhen iz: {net_bridge.__file__}")
    if hasattr(net_bridge, "search"):
        print("      -> Metod .search() nayden.")
    else:
        print("      -> [ALARM] Metod .search() OTSUTSTVUET!")
except ImportError:
    print(" [INFO] modules.net_bridge ne nayden")

try:
    from modules.providers import google_cse_adapter
    print(f" [OK] google_cse_adapter zagruzhen iz: {google_cse_adapter.__file__}")
except ImportError:
    print(" [FAIL] google_cse_adapter ne nayden!")

print("\n=== 2. TEST INTERNETA (PRYaMOY VYZOV) ===")
if os.getenv("DIAG_NET_TEST", "0") == "1":
    if 'google_cse_adapter' in locals():
        try:
            res = google_cse_adapter.search("test", limit=1)
            print(f" Rezultat Google: {res}")
        except Exception as e:
            print(f" Oshibka Google: {e}")
    try:
        from modules.web_search import search_web
        res = search_web("test", topk=1)
        print(f" Rezultat web_search: {res}")
    except Exception as e:
        print(f" Oshibka web_search: {e}")
else:
    print(" [SKIP] DIAG_NET_TEST=0 (setevoy test otklyuchen)")

print("\n=== 3. TEST PROVAYDERA (LLM) ===")
if os.getenv("DIAG_LLM_TEST", "0") == "1":
    try:
        from modules.providers import registry
        print(" Otpravlyaem testovyy zapros v LLM (mode=judge)...")
        msg = [{"role": "user", "content": "Ping"}]
        res = registry.answer(messages=msg, mode="judge")
        print(f" Otvet provaydera: {res}")
    except Exception as e:
        print(f" Oshibka provaydera: {e}")
else:
    print(" [SKIP] DIAG_LLM_TEST=0 (LLM test otklyuchen)")

print("\n=== KONETs DIAGNOSTIKI ===")