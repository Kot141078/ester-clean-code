import os
import re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET = "run_ester_fixed.py"

# POLNYY BLOK KONFIGURATsII (Original + Internet V7)
FULL_CONFIG_BLOCK = """
# ==========================================
# --- ESTER CORE CONFIGURATION (RESTORED) ---
# ==========================================

# 1. VOLITION & SLEEP
VOLITION_TICK_SEC = 20
VOLITION_FIRST_SEC = 5
VOLITION_MISFIRE_GRACE = 60
VOLITION_DEBUG = True
SLEEP_THRESHOLD_SEC = 20
DREAM_FALLBACK_ADMIN_CHAT = True   # Razreshit pisat adminu, esli skuchno

# 2. MEMORY & LIMITS
DEDUP_MAXLEN = 1000
SHORT_TERM_MAXLEN = 50
SHORT_TERM_TTL_SEC = 259200        # 3 days
MAX_MEMORY_CHARS = 12000           # Limit for RAG recall
TIMEOUT_CAP = 3600                 # Deep Thinking max duration

# 3. DREAM & GENERATION
DREAM_FORCE_LOCAL = False
DREAM_PASSES = 1
DREAM_TEMPERATURE = 0.7
DREAM_MAX_TOKENS = 4000            # For thought process
DREAM_MIN_INTERVAL_SEC = 10
DREAM_CONTEXT_ITEMS = 15
DREAM_CONTEXT_CHARS = 60000
DREAM_MAX_PROMPT_CHARS = 128000
MAX_OUT_TOKENS = 4096              # For final answer
DEFAULT_TEMP = 0.7

# 4. SOCIAL & CURIOSITY
SOCIAL_PROB = 0.01                 # P2P broadcast probability
CURIOSITY_MIN_INTERVAL_SEC = 600   # Self-questioning interval
CURIOSITY_PROBABILITY = 0.1

# 5. CASCADE & REFLECTION
CASCADE_REPLY_ENABLED = True
CASCADE_REPLY_STEPS = 1
PROACTIVE_RULES_PATH = "data/policy/proactive.json"

# 6. WEB & SEARCH (V7 NEW)
WEB_TIMEOUT_SEC = 10
WEB_MAX_RPM = 10
CLOSED_BOX = False                 # INTERNET ON
WEB_FACTCHECK = "always"
SELF_SEARCH_SMART = True
SELF_SEARCH_MIN_INTERVAL = 300
SELF_SEARCH_MAX_PER_HOUR = 10
# ==========================================
"""

def restore_full_config():
    if not os.path.exists(TARGET):
        print(f"File {TARGET} not found!")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Ochistka: Udalyaem nashi predyduschie "zaplatki", chtoby ne bylo dubley
    # Udalyaem stroki, nachinayuschiesya s nashikh peremennykh, esli oni uzhe est v kode
    # (Eto grubaya, no deystvennaya ochistka "musora" ot khotfiksov)
    lines = content.splitlines()
    clean_lines = []
    
    # Spisok peremennykh, kotorye my pereopredelyaem
    vars_to_reset = [
        "VOLITION_TICK_SEC", "VOLITION_FIRST_SEC", "VOLITION_MISFIRE_GRACE", "VOLITION_DEBUG",
        "SLEEP_THRESHOLD_SEC", "DREAM_FALLBACK_ADMIN_CHAT",
        "DEDUP_MAXLEN", "SHORT_TERM_MAXLEN", "SHORT_TERM_TTL_SEC", "MAX_MEMORY_CHARS", "TIMEOUT_CAP",
        "DREAM_FORCE_LOCAL", "DREAM_PASSES", "DREAM_TEMPERATURE", "DREAM_MAX_TOKENS",
        "DREAM_MIN_INTERVAL_SEC", "DREAM_CONTEXT_ITEMS", "DREAM_CONTEXT_CHARS", "DREAM_MAX_PROMPT_CHARS",
        "MAX_OUT_TOKENS", "DEFAULT_TEMP",
        "SOCIAL_PROB", "CURIOSITY_MIN_INTERVAL_SEC", "CURIOSITY_PROBABILITY",
        "CASCADE_REPLY_ENABLED", "CASCADE_REPLY_STEPS", "PROACTIVE_RULES_PATH",
        "WEB_TIMEOUT_SEC", "WEB_MAX_RPM", "SELF_SEARCH_MIN_INTERVAL"
    ]
    
    for line in lines:
        is_duplicate = False
        for v in vars_to_reset:
            # Esli stroka nachinaetsya s obyavleniya peremennoy (naprimer "TIMEOUT_CAP =")
            # i eto NE nash novyy blok (my ego esche ne vstavili)
            if line.strip().startswith(v + " =") or line.strip().startswith(v + "="):
                is_duplicate = True
                break
        
        if not is_duplicate:
            clean_lines.append(line)

    content = "\n".join(clean_lines)

    # 2. Vstavka: Pomeschaem polnyy blok srazu posle importov
    if "from dotenv import load_dotenv" in content:
        # Idealnoe mesto - posle zagruzki .env
        anchor = "from dotenv import load_dotenv"
        new_content = content.replace(anchor, anchor + "\n" + FULL_CONFIG_BLOCK)
    elif "import os" in content:
        anchor = "import os"
        new_content = content.replace(anchor, anchor + "\n" + FULL_CONFIG_BLOCK)
    else:
        new_content = FULL_CONFIG_BLOCK + "\n" + content

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"✅ FULL CONFIGURATION RESTORED in {TARGET}")

if __name__ == "__main__":
    restore_full_config()