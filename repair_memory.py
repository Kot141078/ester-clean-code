import os

TARGET = "run_ester_fixed.py"

# 1. Fixed restore function (uses dist rather than non-existent class)
NEW_RESTORE_FUNC = r"""
def restore_context_from_passport():
    # --- ESTER MEMORY RECALL (PASSPORT V2) ---
    passport_path = r"<repo-root>\data\passport\clean_memory.jsonl"
    if not os.path.exists(passport_path):
        logging.info(f"[MEMORY] No passport found at {passport_path}")
        return

    logging.info(f"[MEMORY] Reading passport: {passport_path} ...")
    count = 0
    try:
        target_uid = int(os.getenv("ADMIN_ID", 0))
        if target_uid == 0:
            return
        
        mem_key = (int(target_uid), int(target_uid)) # Predpolagaem chat_id=user_id dlya lichki, ili ischem v logakh
        # No luchshe brat chat_id iz loga. Poka uprostim: vosstanavlivaem v "lichnyy kontekst" admina.
        # V kode get_short_term trebuet (chat_id, user_id).
        # Heuristic: If it's a private chat, they match.
        
        # It’s better this way: just fill out the _short_term_by_key for the admin, assuming that he is writing from his account.
        # We need to know the chat_id. Isn't it in clean_memory.jsonl?
        # It's not in the old records. In new ones we can write it, but for now we read what is there.
        # Let's say we restore the context for (ADMIN_ID, ADMIN_ID).
        
        if mem_key not in _short_term_by_key:
            _short_term_by_key[mem_key] = deque(maxlen=SHORT_TERM_MAXLEN)
        q = _short_term_by_key[mem_key]
        
        with open(passport_path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-SHORT_TERM_MAXLEN:]
            
        for line in lines:
            try:
                rec = json.loads(line)
                if "role_user" in rec:
                    q.append({"role": "user", "content": rec["role_user"]})
                    count += 1
                if "role_assistant" in rec:
                    q.append({"role": "assistant", "content": rec["role_assistant"]})
                    count += 1
                if "role_system" in rec:
                    # Thoughts also load, but as systems (if the bot can read them)
                    pass 
            except: pass
            
        logging.info(f"[MEMORY] ✨ Restored {count} thoughts from Passport into RAM.")
    except Exception as e:
        logging.error(f"[MEMORY] Restore error: {e}")
"""

def repair_memory():
    if not os.path.exists(TARGET):
        print("Target not found.")
        return

    with open(TARGET, "r", encoding="utf-8") as f:
        content = f.read()

    # A. Replacing the broken recovery function
    # Ischem ee po zagolovku
    if "def restore_context_from_passport():" in content:
        # Trying to find the entire block until the next function or end
        # This is a complicated regex, so let's replace the "old piece" with the "new" one,
        # relying on unique strings inside the old function.
        
        # Unique string in the OLD function (from your log): "ShortTermItet"
        # If it is, then the function is old and broken.
        if "ShortTermItem" in content:
            print("🔧 Fixing broken restore function (removing ShortTermItem)...")
            # Finding the beginning of the function
            start_idx = content.find("def restore_context_from_passport():")
            # We find the end (the beginning of the next function chesk_fatigue_levels or main)
            end_idx = content.find("async def check_fatigue_levels", start_idx)
            if end_idx == -1:
                end_idx = content.find("def main():", start_idx)
            
            if start_idx != -1 and end_idx != -1:
                old_block = content[start_idx:end_idx]
                content = content.replace(old_block, NEW_RESTORE_FUNC + "\n\n\n")
                print("✅ Restore function replaced.")
    else:
        print("⚠️ Restore function not found. Injecting...")
        content = content.replace("def main():", NEW_RESTORE_FUNC + "\n\ndef main():")

    # B. We implement an entry in the handle_message (Persistence)
    # 1. User entry
    # Ischem: st.append({"role": "user", "content": text})
    user_hook_marker = 'st.append({"role": "user", "content": text})'
    if user_hook_marker in content and '_persist_to_passport("user", text)' not in content:
        content = content.replace(
            user_hook_marker, 
            user_hook_marker + '\n    _persist_to_passport("user", text)'
        )
        print("✅ User memory hook installed.")
    
    # 2. Zapis bota
    # Ischem: st.append({"role": "assistant", "content": final_text})
    bot_hook_marker = 'st.append({"role": "assistant", "content": final_text})'
    if bot_hook_marker in content and '_persist_to_passport("assistant", final_text)' not in content:
        content = content.replace(
            bot_hook_marker,
            bot_hook_marker + '\n        _persist_to_passport("assistant", final_text)'
        )
        print("✅ Assistant memory hook installed.")

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(content)
    
    print("🚀 Memory I/O Repair Complete.")

if __name__ == "__main__":
    repair_memory()
