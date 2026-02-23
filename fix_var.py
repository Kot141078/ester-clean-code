from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

def fix_missing_var():
    if not os.path.exists(TARGET):
        print(f"File {TARGET} not found!")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    # Proveryaem, est li uzhe opredelenie (chtoby ne dublirovat, esli prichina v drugom)
    if "DEDUP_MAXLEN =" in content:
        print("ℹ️ DEDUP_MAXLEN found in text, but maybe out of scope. Moving/Injecting to top.")
        # Esli ona est, no gde-to vnizu, Python ee ne vidit na moment initsializatsii.
        # Poetomu my vse ravno dobavim strakhovochnuyu kopiyu naverkhu.

    # Vstavlyaem peremennuyu posle importov
    # Ischem "import os" ili "import sys" ili prosto nachalo
    
    # Konstanta dlya dliny ocheredi soobscheniy (1000 khvatit za glaza)
    fix_line = "\nDEDUP_MAXLEN = 1000  # Restored by Hotfix\n"
    
    if "import os" in content:
        content = content.replace("import os", "import os" + fix_line, 1)
    else:
        # Esli vdrug import os net, vstavlyaem v nachalo
        content = fix_line + content

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"✅ Variable DEDUP_MAXLEN restored in {TARGET}")

if __name__ == "__main__":
    fix_missing_var()