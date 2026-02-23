from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

# Vosstanavlivaem nastroyki refleksii
CASCADE_BLOCK = """
# --- CASCADE CONFIG ---
CASCADE_REPLY_ENABLED = True  # Enable multi-step thinking
CASCADE_REPLY_STEPS = 1       # Default depth
PROACTIVE_RULES_PATH = "data/policy/proactive.json"
# ----------------------
"""

def fix_cascade():
    if not os.path.exists(TARGET):
        print(f"File {TARGET} not found!")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    if "CASCADE_REPLY_ENABLED =" in content:
        print("✅ Cascade config already present.")
        return

    # Vstavlyaem posle import os
    if "import os" in content:
        new_content = content.replace("import os", "import os\n" + CASCADE_BLOCK, 1)
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Cascade config injected into {TARGET}")
    else:
        new_content = CASCADE_BLOCK + "\n" + content
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Cascade config prepended to {TARGET}")

if __name__ == "__main__":
    fix_cascade()