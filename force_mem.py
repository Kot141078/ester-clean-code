import os
import re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET = "run_ester_fixed.py"

def force_memory_limit():
    if not os.path.exists(TARGET):
        print("Target not found.")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    replaced_count = 0
    
    for line in lines:
        # Ischem lyubuyu stroku, gde prisvaivaetsya SHORT_TERM_MAXLEN
        # (ignoriruem kommentarii, esli oni ne v nachale stroki)
        if line.strip().startswith("SHORT_TERM_MAXLEN ="):
            # Zamenyaem na 500, sokhranyaya kommentarii esli byli
            if "#" in line:
                comment = line.split("#", 1)[1].strip()
                new_lines.append(f"SHORT_TERM_MAXLEN = 500  # {comment} (Forced Fix)\n")
            else:
                new_lines.append("SHORT_TERM_MAXLEN = 500  # Forced Fix\n")
            replaced_count += 1
        else:
            new_lines.append(line)

    with open(TARGET, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    print(f"✅ Replaced {replaced_count} occurrences of SHORT_TERM_MAXLEN with 500.")

if __name__ == "__main__":
    force_memory_limit()