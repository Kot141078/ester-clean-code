from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

CURIOSITY_BLOCK = """
# --- CURIOSITY CONFIG ---
CURIOSITY_MIN_INTERVAL_SEC = 600  # 10 minutes between self-questions
CURIOSITY_PROBABILITY = 0.1       # 10% chance to act curious
# ------------------------
"""

def fix_curiosity():
    if not os.path.exists(TARGET):
        print(f"File {TARGET} not found!")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    if "CURIOSITY_MIN_INTERVAL_SEC =" in content:
        print("✅ Curiosity config already present.")
        return

    # Vstavlyaem posle import os
    if "import os" in content:
        new_content = content.replace("import os", "import os\n" + CURIOSITY_BLOCK, 1)
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Curiosity config injected into {TARGET}")
    else:
        # Fallback
        new_content = CURIOSITY_BLOCK + "\n" + content
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Curiosity config prepended to {TARGET}")

if __name__ == "__main__":
    fix_curiosity()