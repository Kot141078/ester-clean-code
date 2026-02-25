from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

def fix_missing_var():
    if not os.path.exists(TARGET):
        print(f"File {TARGET} not found!")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    # We check if there is already a definition (so as not to duplicate if the reason is different)
    if "DEDUP_MAXLEN =" in content:
        print("ℹ️ DEDUP_MAXLEN found in text, but maybe out of scope. Moving/Injecting to top.")
        # If it exists, but somewhere below, Potkhon does not see it at the time of initialization.
        # So we'll still add a safety copy at the top.

    # Inserting a variable after imports
    # We are looking for “os import” or “sys import” or just the beginning
    
    # Constant for the length of the message queue (1000 is enough)
    fix_line = "\nDEDUP_MAXLEN = 1000  # Restored by Hotfix\n"
    
    if "import os" in content:
        content = content.replace("import os", "import os" + fix_line, 1)
    else:
        # If suddenly there is no OS import, insert it at the beginning
        content = fix_line + content

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"✅ Variable DEDUP_MAXLEN restored in {TARGET}")

if __name__ == "__main__":
    fix_missing_var()