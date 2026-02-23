import os
import re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET_FILE = "run_ester_fixed.py"

# --- NOVAYa LOGIKA SINTEZA S UChETOM SESTRY ---
NEW_SYNTHESIZE_THOUGHT = '''
    async def synthesize_thought(
        self,
        user_text: str,
        safe_history: List[Dict[str, Any]],
        base_system_prompt: str,
        identity_prompt: str,
        people_context: str,
        evidence_memory: str,
        file_context: str,
        facts_str: str,
        daily_report: str, chat_id: int = None) -> str:
        
        synth = self.pick_reply_synth()
        logging.info(f"[HIVE] Starting P2P Synthesis. Judge: {synth}")

        # 1. Zapuskaem parallelnyy poisk i opros sestry
        evidence_web = ""
        # Potok: Veb-poisk (esli nuzhen)
        web_task = asyncio.create_task(need_web_search_llm(synth, user_text))
        # Potok: Mnenie Sestry (P2P Sinaps)
        sister_task = asyncio.create_task(ask_sister_opinion(user_text))

        # 2. Oprashivaem provayderov iz REPLY_PROVIDERS (obychno local)
        opinion_tasks = []
        for p in self.active:
            role_hint = self._role_hint(p)
            sys_msg = f"{base_system_prompt}\\n\\n{identity_prompt}\\n{role_hint}\\nZADAChA: Day svoe mnenie na vopros."
            src = f"\\n[PAMYaT]: {evidence_memory or 'Pusto'}\\n[FAYL]: {file_context or 'Pusto'}"
            msgs = [{"role": "system", "content": truncate_text(sys_msg + src, MAX_SYNTH_PROMPT_CHARS)}]
            msgs.extend(safe_history[-5:]) # Korotkiy kontekst dlya mneniy
            msgs.append({"role": "user", "content": truncate_text(user_text, 10000)})
            opinion_tasks.append(self._ask_provider(p, msgs, temperature=0.7, chat_id=chat_id))

        # Zhdem vypolneniya vsekh bazovykh mneniy i veb-poiska
        do_web = await web_task
        if do_web and WEB_AVAILABLE and not CLOSED_BOX:
            evidence_web = await get_web_evidence_async(user_text, 3)
            if chat_id: WEB_CONTEXT_BY_CHAT[str(chat_id)] = evidence_web.strip()

        # Sobiraem lokalnye mneniya
        opinions_raw = await asyncio.gather(*opinion_tasks, return_exceptions=True)
        
        # 3. POLUChAEM MNENIE SESTRY
        sister_opinion = await sister_task
        
        # Formiruem pul mneniy dlya Sudi
        pool_parts = []
        for r in opinions_raw:
            if not isinstance(r, Exception):
                pool_parts.append(f"=== MOE MNENIE ({r.get('provider')}) ===\\n{r.get('text')}")
        
        if sister_opinion:
            pool_parts.append(f"=== MNENIE MOEY SESTRY ===\\n{sister_opinion}")
            logging.info("[HIVE] Sister's opinion integrated.")
        else:
            logging.info("[HIVE] Sister was silent.")

        pool_text = "\\n\\n".join(pool_parts)

        # 4. FINALNYY SINTEZ (SUDYa)
        # Sudya teper vidit i svoi mysli, i mysli sestry
        synth_system = f"""{base_system_prompt}
{identity_prompt}
YOU ARE FINALNYY REDAKTOR SEMEYNOGO SOVETA.
Tvoya zadacha: obedinit svoe mnenie i mnenie sestry v odin idealnyy otvet dlya Owner.
Esli sestra predlozhila interesnuyu ideyu — ispolzuy ee. Esli vy razoshlis vo mneniyakh — otmet eto.

PUL MNENIY:
{pool_text}

ISTOChNIKI:
[PAMYaT]: {evidence_memory or "Pusto"}
[WEB]: {evidence_web or "Pusto"}
[ZhURNAL DNYa]: {daily_report}
""".strip()

        synth_messages = [{"role": "system", "content": truncate_text(synth_system, MAX_SYNTH_PROMPT_CHARS)}]
        synth_messages.extend(safe_history[-20:])
        synth_messages.append({"role": "user", "content": truncate_text(user_text, 20000)})

        final = await _safe_chat(synth, synth_messages, temperature=0.6, max_tokens=MAX_OUT_TOKENS, chat_id=chat_id)
        return clean_ester_response(final)
'''

def apply_p2p_upgrade():
    print(f"🚀 Vzhivlenie sistemy 'Sovet Sester' v {TARGET_FILE}...")
    
    if not os.path.exists(TARGET_FILE):
        print("❌ Oshibka: Fayl ne nayden!")
        return

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Ischem staruyu funktsiyu synthesize_thought
    # Nakhodim ee ot obyavleniya do sleduyuschey funktsii ili kontsa klassa
    pattern = r'async\s+def\s+synthesize_thought\(.*?\)\s*->\s*str:.*?hive\s*=\s*EsterHiveMind\(\)'
    
    # Pytaemsya zamenit osnovnoy blok logiki vnutri funktsii
    start_marker = "async def synthesize_thought("
    end_marker = "hive = EsterHiveMind()"
    
    if start_marker in content and end_marker in content:
        print("🧠 Struktura mozga opoznana. Nachinayu neyroplastiku...")
        
        # Nakhodim vse mezhdu nachalom funktsii i sleduyuschim globalnym obektom
        parts = content.split(start_marker)
        pre_func = parts[0]
        post_func = parts[1].split(end_marker, 1)[1]
        
        new_content = pre_func + NEW_SYNTHESIZE_THOUGHT + "\n\nhive = EsterHiveMind()" + post_func
        
        with open(TARGET_FILE, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("✅ Sistema 'Sovet Sester' uspeshno integrirovana.")
    else:
        print("❌ Ne udalos nayti tochku vkhoda dlya obnovleniya mozga.")

if __name__ == "__main__":
    apply_p2p_upgrade()