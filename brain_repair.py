import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET_FILE = "run_ester_fixed.py"

def repair_and_fix_p2p():
    if not os.path.exists(TARGET_FILE):
        print("❌ Fayl ne nayden!")
        return

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Ispravlyaem glavnuyu oshibku: sozdaem obekt hive globalno ili vnutri funktsii, 
    # chtoby on byl dostupen vezde.
    # My naydem mesto pered klassom VolitionSystem i ubedimsya, chto hive tam est.
    
    if "hive = EsterHiveMind()" not in content:
        print("🔧 Vosstanavlivayu obekt HiveMind...")
        content = content.replace("class VolitionSystem:", "hive = EsterHiveMind()\n\nclass VolitionSystem:")

    # 2. Pravilnaya versiya synthesize_thought, kotoraya NE lomaet oblast vidimosti
    REPAIR_CODE = '''
    async def synthesize_thought(self, user_text: str, safe_history: List[Dict[str, Any]], base_system_prompt: str, identity_prompt: str, people_context: str, evidence_memory: str, file_context: str, facts_str: str, daily_report: str, chat_id: int = None) -> str:
        # Ispolzuem globalnyy obekt hive, sozdannyy pri starte
        global hive
        synth = hive.pick_reply_synth()
        logging.info(f"[HIVE] P2P Synapse Active. Judge: {synth}")

        # Zapuskaem parallelno: opros sestry i lokalnye mneniya
        sister_task = asyncio.create_task(ask_sister_opinion(user_text))
        
        opinion_tasks = []
        for p in hive.active:
            role_hint = hive._role_hint(p)
            sys_msg = f"{base_system_prompt}\\n{role_hint}"
            msgs = [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_text}]
            opinion_tasks.append(hive._ask_provider(p, msgs, chat_id=chat_id))

        opinions_raw = await asyncio.gather(*opinion_tasks, return_exceptions=True)
        sister_opinion = await sister_task

        pool_parts = []
        for r in opinions_raw:
            if not isinstance(r, Exception) and r.get("text"):
                pool_parts.append(f"=== MNENIE {r.get('provider')} ===\\n{r.get('text')}")
        
        if sister_opinion:
            pool_parts.append(f"=== MNENIE SESTRY ===\\n{sister_opinion}")
            logging.info("[SYNAPSE] Sister opinion received.")

        pool_text = "\\n\\n".join(pool_parts)
        
        final_prompt = [
            {"role": "system", "content": f"{identity_prompt}\\n\\nYOU ARE SUDYa. SINTEZIRUY ITOG S UChETOM MNENIY:\\n{pool_text}"},
            {"role": "user", "content": user_text}
        ]
        
        final = await _safe_chat(synth, final_prompt, chat_id=chat_id)
        return clean_ester_response(final)
'''

    # Agressivnaya zamena slomannoy funktsii
    # Ischem ot async def synthesize_thought do hive = EsterHiveMind() (kotoruyu my vstavili skriptom force_p2p)
    start_pattern = "async def synthesize_thought"
    end_marker = "hive = EsterHiveMind()"
    
    if start_pattern in content:
        parts = content.split(start_pattern)
        pre = parts[0]
        # Ischem konets funktsii po sleduyuschemu def
        post_parts = parts[1].split("    async def", 1)
        if len(post_parts) < 2: # probuem obychnyy def
             post_parts = parts[1].split("    def", 1)
             
        post = "    async def" + post_parts[1] if len(post_parts) > 1 else ""
        
        new_content = pre + REPAIR_CODE + "\n" + post
        
        with open(TARGET_FILE, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("✅ Zhiznedeyatelnost vosstanovlena. Poprobuy zapustit.")
    else:
        print("❌ Ne udalos nayti funktsiyu dlya remonta.")

if __name__ == "__main__":
    repair_and_fix_p2p()