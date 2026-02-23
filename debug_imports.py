import sys
import os
import logging
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

print("=== PROVERKA IMPORTOV ADAPTEROV ===\n")

def try_import(module_name):
    print(f"Popytka importa: {module_name} ...", end=" ")
    try:
        __import__(module_name)
        print("✅ OK")
        return True
    except ImportError as e:
        print(f"❌ FAIL: {e}")
        return False
    except Exception as e:
        print(f"❌ CRITICAL: {e}")
        return False

# 1. Proveryaem biblioteki
print("--- 1. Biblioteki Python ---")
libs = ["openai", "google.generativeai"]
for l in libs:
    try_import(l)

# 2. Proveryaem fayly adapterov
print("\n--- 2. Vnutrennie moduli Ester ---")
adapters = [
    "modules.providers.openai_adapter",
    "modules.providers.gemini_adapter",
    "modules.providers.registry"
]

for a in adapters:
    try_import(a)

print("\n=== KONETs ===")