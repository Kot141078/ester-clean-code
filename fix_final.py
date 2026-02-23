from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

# Blok vsekh vozmozhnykh "poteryashek" na osnove tvoego .env i koda
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

    # Proveryaem glavnogo vinovnika
    if "SLEEP_THRESHOLD_SEC =" in content:
        print("✅ SLEEP_THRESHOLD_SEC already present.")
        return

    # Vstavlyaem posle import os (ili v nachalo, esli ne naydem)
    if "import os" in content:
        new_content = content.replace("import os", "import os\n" + MISSING_BLOCK, 1)
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Final config block injected into {TARGET}")
    else:
        # Fallback: vstavlyaem v samoe nachalo
        new_content = MISSING_BLOCK + "\n" + content
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Final config block prepended to {TARGET}")

if __name__ == "__main__":
    fix_final_vars()