from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

RESTORE_GEN_BLOCK = """
# --- GENERATION CONSTANTS ---
MAX_OUT_TOKENS = 4096
DEFAULT_TEMP = 0.7
# ----------------------------
"""

def fix_gen_constants():
    if not os.path.exists(TARGET):
        print(f"File {TARGET} not found!")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    if "MAX_OUT_TOKENS =" in content:
        print("✅ MAX_OUT_TOKENS already present.")
        return

    # Vstavlyaem srazu posle import os (tuda zhe, gde ostalnye)
    if "import os" in content:
        new_content = content.replace("import os", "import os\n" + RESTORE_GEN_BLOCK, 1)
        
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Generation constants injected into {TARGET}")
    else:
        print("❌ Could not find anchor to inject constants.")

if __name__ == "__main__":
    fix_gen_constants()