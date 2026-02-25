import sys
import os
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Adds the current folder to the path so that imports work
sys.path.append(os.getcwd())

try:
    from modules.mem.passport import get_identity_system_prompt, PASSPORT_MD_PATH
    
    print(f"--- DIAGNOSTIKA PASPORTA ---")
    print(f"Ozhidaemyy put: {PASSPORT_MD_PATH}")
    print(f"Does the file exist? ZZF0Z")
    
    if PASSPORT_MD_PATH.exists():
        print(f"Razmer fayla: {PASSPORT_MD_PATH.stat().st_size} bayt")
        
    prompt = get_identity_system_prompt()
    print("--- WHAT ESTHER SEES (System Prompt) ---")
    print(prompt[:500] + "...\n(obrezano)")
    print("---------------------------------------")
    
    if "Owner" in prompt:
        print("ITOG: ✅ Imya 'Owner' EST v prompte.")
    else:
        print("ITOG: ❌ Imeni NET v prompte. Zagruzhaetsya zaglushka!")

except Exception as e:
    print(f"IMPORT OR EXECUTION Error: ZZF0Z")