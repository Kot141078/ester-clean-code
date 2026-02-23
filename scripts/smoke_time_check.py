# scripts/smoke_time_check.py
import sys
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Dobavlyaem koren proekta v put
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from modules.self import time_utils
    from modules.self import engine_identity
    print("✅ Modules imported successfully.")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

def test():
    iso, human = time_utils.format_for_prompt()
    print(f"\n[Time Check]")
    print(f"ISO:   {iso}")
    print(f"Human: {human}")
    
    if "DefaultCity" not in str(time_utils.HOME_TZ):
        print("❌ Error: Timezone is not DefaultCity!")
    else:
        print("✅ Timezone is DefaultCity.")

    print(f"\n[Engine Identity Check]")
    label = engine_identity.engine_label("lmstudio_ctx")
    print(f"lmstudio_ctx -> {label}")
    if "lokalnaya" in label:
        print("✅ Labeling works.")
    else:
        print("❌ Labeling failed.")

if __name__ == "__main__":
    test()