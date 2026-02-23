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
        # 1. Otslezhivaem, nakhodimsya li my vnutri funktsii vosstanovleniya
        if "def restore_context_from_passport" in line:
            in_restore_func = True
        
        # Esli doshli do sleduyuschey funktsii (obychno main), vykhodim iz rezhima otslezhivaniya
        if "def main():" in line:
            in_restore_func = False

        # 2. Esli my vnutri restore_context_from_passport...
        if in_restore_func:
            # ...i vidim popytku zapisi v profile s peremennoy 'rec' (priznak chteniya)
            if "_persist_to_passport" in line and ("rec[\"role_user\"]" in line or "rec[\"role_assistant\"]" in line):
                # ETO OShIBKA. Udalyaem etu stroku.
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