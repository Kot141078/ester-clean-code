import os

TARGET = "run_ester_fixed.py"

def align_memory_hooks():
    if not os.path.exists(TARGET):
        print("Target not found.")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    fixed_count = 0
    
    for i, line in enumerate(lines):
        # 1. Ispravlyaem khuk Assistenta (assistant hook)
        if '_persist_to_passport("assistant", final_text)' in line:
            # Smotrim na otstup predyduschey stroki (st.append)
            prev_line = lines[i-1]
            if "st.append" in prev_line:
                # Vychislyaem otstup predyduschey stroki
                indent = len(prev_line) - len(prev_line.lstrip())
                # Sozdaem novuyu stroku s takim zhe otstupom
                current_indent = len(line) - len(line.lstrip())
                
                if current_indent != indent:
                    new_line = (" " * indent) + line.lstrip()
                    new_lines.append(new_line)
                    fixed_count += 1
                    continue

        # 2. Ispravlyaem khuk Polzovatelya (user hook)
        if '_persist_to_passport("user", text)' in line:
            prev_line = lines[i-1]
            if "st.append" in prev_line:
                indent = len(prev_line) - len(prev_line.lstrip())
                current_indent = len(line) - len(line.lstrip())
                
                if current_indent != indent:
                    new_line = (" " * indent) + line.lstrip()
                    new_lines.append(new_line)
                    fixed_count += 1
                    continue

        new_lines.append(line)

    with open(TARGET, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    print(f"✅ Re-aligned {fixed_count} memory hook lines.")

if __name__ == "__main__":
    align_memory_hooks()
