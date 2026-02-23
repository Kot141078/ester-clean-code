import sys
import os
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Dobavlyaem tekuschuyu papku v put, chtoby importy rabotali
sys.path.append(os.getcwd())

try:
    from modules.mem.passport import get_identity_system_prompt, PASSPORT_MD_PATH
    
    print(f"--- DIAGNOSTIKA PASPORTA ---")
    print(f"Ozhidaemyy put: {PASSPORT_MD_PATH}")
    print(f"Fayl suschestvuet? {PASSPORT_MD_PATH.exists()}")
    
    if PASSPORT_MD_PATH.exists():
        print(f"Razmer fayla: {PASSPORT_MD_PATH.stat().st_size} bayt")
        
    prompt = get_identity_system_prompt()
    print("\n--- ChTO VIDIT ESTER (System Prompt) ---")
    print(prompt[:500] + "...\n(obrezano)")
    print("---------------------------------------")
    
    if "Owner" in prompt:
        print("ITOG: ✅ Imya 'Owner' EST v prompte.")
    else:
        print("ITOG: ❌ Imeni NET v prompte. Zagruzhaetsya zaglushka!")

except Exception as e:
    print(f"OShIBKA IMPORTA ILI VYPOLNENIYa: {e}")