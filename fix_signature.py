import os
import re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET = "run_ester_fixed.py"

def repair_signatures():
    if not os.path.exists(TARGET):
        print("Target not found.")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    print("🔧 Scanning for broken signatures...")
    
    # 1. Ispravlyaem synthesize_thought
    # Ischem: async def synthesize_thought(..... daily_report: str) -> str:
    # Task: insert ", chat_id: int = None" before the closing parenthesis
    
    # Regular searches for the end of the function arguments, where there is a dialo_report
    # (daily_report: str) ... (anything) ... ) -> str
    pattern_synth = r"(daily_report:\s*str)(\s*,?\s*)(\)\s*->\s*str:)"
    
    # Checking if there is already a chat_id in this function
    # Berem kusok teksta ot def synthesize_thought do -> str
    synth_match = re.search(r"def synthesize_thought.*?->\s*str:", content, re.DOTALL)
    if synth_match:
        if "chat_id" not in synth_match.group(0):
            print("⚠️ synthesize_thought is missing chat_id. Fixing...")
            content = re.sub(pattern_synth, r"\1, chat_id: int = None\3", content, count=1)
        else:
            print("✅ synthesize_thought already has chat_id.")
    else:
        print("❌ Could not find synthesize_thought definition!")

    # 2. Ispravlyaem _ask_provider
    # Ischem: temperature: float) -> Dict
    pattern_ask = r"(temperature:\s*float)(\s*\)\s*->\s*Dict)"
    
    ask_match = re.search(r"def _ask_provider.*?->\s*Dict", content, re.DOTALL)
    if ask_match:
        if "chat_id" not in ask_match.group(0):
             print("⚠️ _ask_provider is missing chat_id. Fixing...")
             content = re.sub(pattern_ask, r"\1, chat_id: int = None\2", content, count=1)
        else:
            print("✅ _ask_provider already has chat_id.")

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(content)
    
    print("🚀 Signatures repaired.")

if __name__ == "__main__":
    repair_signatures()