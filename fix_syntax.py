from modules.memory.facade import memory_add, ESTER_MEM_FACADE
import os

TARGET = "run_ester_fixed.py"

def fix_syntax_error():
    if not os.path.exists(TARGET):
        print("Target not found.")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    in_restore_func = False
    deleted_count = 0

    for line in lines:
        # 1. We monitor whether we are inside the recovery function
        if "def restore_context_from_passport" in line:
            in_restore_func = True
        
        # If we reach the next function (usually main), we exit the tracking mode
        if "def main():" in line:
            in_restore_func = False

        # 2. If you are inside the restaurant_context_from_passport...
        if in_restore_func:
            # ...and we see an attempt to write to the profile with the variable (reading sign)
            if "_persist_to_passport" in line and ("rec[\"role_user\"]" in line or "rec[\"role_assistant\"]" in line):
                # THIS IS A Error. Let's delete this line.
                deleted_count += 1
                continue 

        new_lines.append(line)

    with open(TARGET, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    if deleted_count > 0:
        print(f"✅ Surgically removed {deleted_count} erroneous lines causing SyntaxError.")
    else:
        print("⚠️ No erroneous lines found (maybe already fixed?).")

if __name__ == "__main__":
    fix_syntax_error()