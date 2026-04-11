import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Nastroyka
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("PROV_DIAG")

# Gruzim .env iz kornevoy papki repo
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

print("=== DIAGNOSTIKA MOZGOV (PROVIDERS) ===\n")

# Probuem importirovat reestr
try:
    from modules.providers import registry
    print("[OK] Reestr provayderov nayden.")
except ImportError as e:
    print(f"yuFAILsch Error importing registers: ЗЗФ0З")
    sys.exit(1)

# Funktsiya testa
def test_provider(mode_name):
    print(f"\n--- Test provaydera: '{mode_name}' ---")
    msg = [{"role": "user", "content": "Hello! Are you working? Reply with 'YES'."}]
    
    try:
        # We are trying to get an answer
        res = registry.answer(messages=msg, mode=mode_name)
        
        ans = res.get("text") or res.get("reply") or res.get("answer")
        provider = res.get("provider")
        
        print(f"   Rezultat: {res}")
        
        if ans == "Hello! Are you working? Reply with 'YES'.":
            print("[RESULT]: ⚠️ echo model does not work, returned the question)")
        elif ans:
            print(f"[ITOG]: ✅ WORK! (Answer: {ans})")
        else:
            print("[ITOG]: ❌ PUSTOTA (Oshibka vnutri)")
            
    except Exception as e:
        print(f"[ITOG]: ❌ OShIBKA ISKLYuChENIYa: {e}")

# We run tests on popular modes
modes = ["judge", "openai", "gemini", "cloud", "local"]

for m in modes:
    test_provider(m)

print("\n=== KONETs DIAGNOSTIKI ===")
