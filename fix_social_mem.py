from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

# Vosstanavlivaem nastroyki pamyati i sotsializatsii
FINAL_BLOCK = """
# --- MEMORY & SOCIAL CONFIG ---
SOCIAL_PROB = 0.01        # Low chance to broadcast to P2P
SHORT_TERM_MAXLEN = 50    # Keep last 50 messages in RAM
# ------------------------------
"""

def fix_social_mem():
    if not os.path.exists(TARGET):
        print(f"File {TARGET} not found!")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    if "SHORT_TERM_MAXLEN =" in content:
        print("✅ Config already present.")
        return

    # Vstavlyaem posle import os
    if "import os" in content:
        new_content = content.replace("import os", "import os\n" + FINAL_BLOCK, 1)
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Memory/Social config injected into {TARGET}")
    else:
        new_content = FINAL_BLOCK + "\n" + content
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Memory/Social config prepended to {TARGET}")

if __name__ == "__main__":
    fix_social_mem()