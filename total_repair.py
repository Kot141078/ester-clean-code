import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET_FILE = "run_ester_fixed.py"

def total_repair():
    if not os.path.exists(TARGET_FILE):
        print("❌ Fayl ne nayden!")
        return

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Snachala vyrezaem vse, chto my mogli slomat v rayone synthesize_thought
    # i VolitionSystem, chtoby vstavit chistuyu, rabochuyu versiyu.
    
    # Ischem nachalo nashey problemnoy zony
    if "async def synthesize_thought" in content:
        print("🔧 Nashel povrezhdennyy uchastok. Nachinayu rekonstruktsiyu...")
        
        # Razrezaem fayl do nachala funktsii sinteza
        parts = content.split("async def synthesize_thought", 1)
        pre_content = parts[0]
        
        # Ischem, gde nachinayutsya sistemnye vyzovy v kontse fayla (obychno posle klassov)
        if "if __name__ == \"__main__\":" in parts[1]:
            post_content = "if __name__ == \"__main__\":" + parts[1].split("if __name__ == \"__main__\":")[-1]
        else:
            # Esli ne nashli main, ischem po zapusku voli
            post_content = "will = VolitionSystem()" + parts[1].split("will = VolitionSystem()")[-1]

        # Generiruem pravilnyy blok: Funktsiya Sinteza + Obekt Hive + Klass Voli
        RECONSTRUCTED_BLOCK = '''async def synthesize_thought(self, user_text: str, safe_history: List[Dict[str, Any]], base_system_prompt: str, identity_prompt: str, people_context: str, evidence_memory: str, file_context: str, facts_str: str, daily_report: str, chat_id: int = None) -> str:
        global hive
        synth = hive.pick_reply_synth()
        logging.info(f"[HIVE] P2P Synapse Active. Judge: {synth}")

        # Potok: Mnenie Sestry (P2P Sinaps)
        sister_task = asyncio.create_task(ask_sister_opinion(user_text))
        
        opinion_tasks = []
        for p in hive.active:
            role_hint = hive._role_hint(p)
            msgs = [{"role": "system", "content": f"{base_system_prompt}\\n{role_hint}"}, {"role": "user", "content": user_text}]
            opinion_tasks.append(hive._ask_provider(p, msgs, chat_id=chat_id))

        opinions_raw = await asyncio.gather(*opinion_tasks, return_exceptions=True)
        sister_opinion = await sister_task

        pool_parts = []
        for r in opinions_raw:
            if not isinstance(r, Exception) and r.get("text"):
                pool_parts.append(f"=== MOE MNENIE ({r.get('provider')}) ===\\n{r.get('text')}")
        
        if sister_opinion:
            pool_parts.append(f"=== MNENIE SESTRY ===\\n{sister_opinion}")
            logging.info("[SYNAPSE] Sister opinion integrated.")

        pool_text = "\\n\\n".join(pool_parts)
        
        final_prompt = [
            {"role": "system", "content": f"{identity_prompt}\\n\\nYOU ARE FINALNYY REDAKTOR. SINTEZIRUY SVOE I SESTRINSKOE MNENIE:\\n{pool_text}"},
            {"role": "user", "content": user_text}
        ]
        
        final = await _safe_chat(synth, final_prompt, chat_id=chat_id)
        return clean_ester_response(final)

# Globalnyy obekt dlya dostupa iz vsekh sistem
hive = EsterHiveMind()

class VolitionSystem:
    def __init__(self):
        self.state = "AWAKE"
        self.is_thinking = False
        self.last_tick = time.time()
'''
        # Skleivaem fayl obratno
        # VAZhNO: My sokhranyaem staryy prefiks i postfiks, zamenyaya tolko seredinu
        final_file_content = pre_content + RECONSTRUCTED_BLOCK + "\n\n" + post_content

        with open(TARGET_FILE, 'w', encoding='utf-8') as f:
            f.write(final_file_content)
        print("✅ Sistema vosstanovlena. NameError dolzhen ischeznut.")
    else:
        print("❌ Ne smog nayti tochku vkhoda dlya remonta. Fayl slishkom silno izmenen.")

if __name__ == "__main__":
    total_repair()