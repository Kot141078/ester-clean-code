from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

# Konstanty, kotorye my vosstanavlivaem (soglasno Architecture Roadmap)
RESTORE_BLOCK = """
# --- RESTORED CONSTANTS BLOCK ---
TIMEOUT_CAP = 3600  # 1 hour (Deep Thinking Support)
MAX_WEB_CHARS = 12000  # Context window limit for RAG
DEDUP_MAXLEN = 1000  # Dedup queue size
VOLITION_TICK_SEC = 20
VOLITION_FIRST_SEC = 5
VOLITION_MISFIRE_GRACE = 60
VOLITION_DEBUG = True
DREAM_FORCE_LOCAL = False
DREAM_PASSES = 1
DREAM_TEMPERATURE = 0.7
DREAM_MAX_TOKENS = 4000
DREAM_MIN_INTERVAL_SEC = 10
DREAM_CONTEXT_ITEMS = 15
DREAM_CONTEXT_CHARS = 60000
DREAM_MAX_PROMPT_CHARS = 128000
SELF_SEARCH_MIN_INTERVAL = 300
# -------------------------------
"""

def fix_constants():
    if not os.path.exists(TARGET):
        print(f"File {TARGET} not found!")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    # Spisok peremennykh dlya proverki
    vars_to_check = ["TIMEOUT_CAP", "MAX_WEB_CHARS", "DEDUP_MAXLEN"]
    
    missing_found = False
    for v in vars_to_check:
        if f"{v} =" not in content and f"{v}=" not in content:
            missing_found = True
            print(f"⚠️ Missing critical constant: {v}")

    if not missing_found and "TIMEOUT_CAP" in content:
        print("✅ All constants seem present. No changes needed.")
        return

    # Vstavlyaem blok posle importov (ischem import os)
    if "import os" in content:
        # Vstavlyaem POSLE import os, chtoby navernyaka
        new_content = content.replace("import os", "import os\n" + RESTORE_BLOCK, 1)
        
        # Esli DEDUP_MAXLEN uzhe byl dobavlen proshlym fiksom, on prosto pereopredelitsya (ne strashno),
        # ili mozhno vychistit dubli, no Python eto prostit.
        
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"✅ Critical constants injected into {TARGET}")
    else:
        print("❌ Could not find anchor 'import os' to inject constants.")

if __name__ == "__main__":
    fix_constants()