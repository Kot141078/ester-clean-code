from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

def fix_typing_error():
    if not os.path.exists(TARGET):
        print("Target not found.")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    # Looking for the wrong line
    bad_line = "WEB_CONTEXT_BY_CHAT: Dict[str, str] = {}"
    # Change to a simple version (without Dist, so as not to depend on imports)
    good_line = "WEB_CONTEXT_BY_CHAT = {}  # type: ignore"

    if bad_line in content:
        content = content.replace(bad_line, good_line)
        with open(TARGET, "w", encoding="utf-8") as f:
            f.write(content)
        print("✅ Fixed NameError: Removed premature type hint.")
    else:
        print("⚠️ Line not found exactly as expected. Trying 'dict' lower case variant just in case.")
        # In case there are other gaps
        if "WEB_CONTEXT_BY_CHAT" in content and "Dict[" in content:
             content = content.replace("Dict[str, str]", "dict")
             with open(TARGET, "w", encoding="utf-8") as f:
                f.write(content)
             print("✅ Fixed NameError: Changed Dict to dict.")

if __name__ == "__main__":
    fix_typing_error()