import os

TARGET = "run_ester_fixed.py"

# 1. Ispravlennaya funktsiya vosstanovleniya (ispolzuet dict, a ne nesuschestvuyuschiy klass)
NEW_RESTORE_FUNC = r"""
def restore_context_from_passport():
    # --- ESTER MEMORY RECALL (PASSPORT V2) ---
    passport_path = r"D:\ester-project\data\passport\clean_memory.jsonl"
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
        # Evristika: esli eto lichnyy chat, oni sovpadayut.
        
        # Luchshe tak: prosto zapolnim _short_term_by_key dlya admina, predpolagaya, chto on pishet iz svoego akkaunta.
        # Nam nuzhno znat chat_id. V clean_memory.jsonl ego net?
        # V starykh zapisyakh ego net. V novykh my mozhem ego pisat, no poka chitaem to chto est.
        # Dopustim, my vosstanavlivaem kontekst dlya (ADMIN_ID, ADMIN_ID).
        
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
                    # Mysli tozhe gruzim, no kak system (esli bot umeet ikh chitat)
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

    # A. Zamenyaem slomannuyu funktsiyu vosstanovleniya
    # Ischem ee po zagolovku
    if "def restore_context_from_passport():" in content:
        # Pytaemsya nayti ves blok do sleduyuschey funktsii ili kontsa
        # Eto slozhno regex-om, poetomu zamenim "staryy kusok" na "novyy", 
        # opirayas na unikalnye stroki vnutri staroy funktsii.
        
        # Unikalnaya stroka v STAROY funktsii (iz tvoego loga): "ShortTermItem"
        # Esli ona est, znachit funktsiya staraya i slomannaya.
        if "ShortTermItem" in content:
            print("🔧 Fixing broken restore function (removing ShortTermItem)...")
            # Nakhodim nachalo funktsii
            start_idx = content.find("def restore_context_from_passport():")
            # Nakhodim konets (nachalo sleduyuschey funktsii check_fatigue_levels ili main)
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

    # B. Vnedryaem zapis v handle_message (Persistence)
    # 1. Zapis polzovatelya
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
