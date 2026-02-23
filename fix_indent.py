from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

def fix_indentation():
    if not os.path.exists(TARGET):
        print("Target not found.")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    fixed_count = 0
    
    for line in lines:
        # 1. Ispravlyaem vyzov vosstanovleniya
        # Esli vidim 8 probelov pered funktsiey, menyaem na 4
        if line.startswith("        restore_context_from_passport()"):
            new_lines.append("    restore_context_from_passport()\n")
            fixed_count += 1
            continue

        # 2. Ispravlyaem zapusk pollinga (esli on tozhe uekhal)
        if line.startswith("        app.run_polling("):
            new_lines.append(line.replace("        app.run_polling(", "    app.run_polling(", 1))
            fixed_count += 1
            continue
            
        new_lines.append(line)

    with open(TARGET, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    if fixed_count > 0:
        print(f"✅ Fixed indentation on {fixed_count} lines.")
    else:
        print("⚠️ No indentation issues found (or pattern mismatch).")

if __name__ == "__main__":
    fix_indentation()