from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

# Variables that are causing it to fall now
LAST_MILE_BLOCK = """
# --- LAST MILE CONFIG ---
MAX_FILE_CHARS = 20000              # Limit for file reading (RAG)
DREAM_ALLOWED_TYPES = ["text"]      # Allowed output types for dreams
LAST_ADMIN_CHAT_KEY = None          # Runtime state for admin routing
# ------------------------
"""

def fix_last_mile():
    if not os.path.exists(TARGET):
        print(f"File {TARGET} not found!")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    if "MAX_FILE_CHARS =" in content:
        print("✅ Config already present.")
        return

    # Vstavlyaem posle import os
    if "import os" in content:
        new_content = content.replace("import os", "import os\n" + LAST_MILE_BLOCK, 1)
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Last mile config injected into {TARGET}")
    else:
        new_content = LAST_MILE_BLOCK + "\n" + content
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Last mile config prepended to {TARGET}")

if __name__ == "__main__":
    fix_last_mile()