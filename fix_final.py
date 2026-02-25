from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

# Block of all possible “losses” based on your .env and code
MISSING_BLOCK = """
# --- FINAL RESTORED CONFIG ---
SLEEP_THRESHOLD_SEC = 20  # Volition sleep cycle
SHORT_TERM_TTL_SEC = 259200  # 3 days memory
WEB_TIMEOUT_SEC = 10
WEB_MAX_RPM = 10
Admin_ID = 0  # Fallback
# -----------------------------
"""

def fix_final_vars():
    if not os.path.exists(TARGET):
        print(f"File {TARGET} not found!")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    # Let's check the main culprit
    if "SLEEP_THRESHOLD_SEC =" in content:
        print("✅ SLEEP_THRESHOLD_SEC already present.")
        return

    # Paste it after the OS import (or at the beginning, if we don’t find it)
    if "import os" in content:
        new_content = content.replace("import os", "import os\n" + MISSING_BLOCK, 1)
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Final config block injected into {TARGET}")
    else:
        # Falbatsk: insert at the very beginning
        new_content = MISSING_BLOCK + "\n" + content
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Final config block prepended to {TARGET}")

if __name__ == "__main__":
    fix_final_vars()