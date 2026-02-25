import os
import re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET_FILE = "run_ester_fixed.py"

# --- New LOGIC OF SYNTHESIS TAKEN INTO ACCOUNT OF THE SISTER ---
NEW_SYNTHESIZE_THOUGHT = '''async def synthesize_thought(
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

        # 1. We launch a parallel search and survey of the sister
        evidence_web = ""
        # Stream: Web Search (if needed)
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

        # Zhdem vypolneniya vsekh bazovykh mneniy i web-poiska
        do_web = await web_task
        if do_web and WEB_AVAILABLE and not CLOSED_BOX:
            evidence_web = await get_web_evidence_async(user_text, 3)
            if chat_id: WEB_CONTEXT_BY_CHAT[str(chat_id)] = evidence_web.strip()

        # Sobiraem lokalnye mneniya
        opinions_raw = await asyncio.gather(*opinion_tasks, return_exceptions=True)
        
        # 3. POLUCHAEM MNENIE SESTRY
        sister_opinion = await sister_task
        
        # Forming a pool of opinions for the Judge
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

        #4. FINALNYY SINTEZ (SUDYa)
        # Sudya teper vidit i svoi mysli, i mysli sister
        synth_system = f"""{base_system_prompt}
{identity_prompt}
YOU ARE FINALNYY REDAKTOR SEMEYNOGO SOVETA.
Tvoya zadacha: obedinit svoe mnenie i mnenie sisters v odin idealnyy otvet dlya Owner.
Esli sestra predlozhila interesnuyu ideyu — ispolzuy ee. Esli vy razoshlis vo mneniyakh - otmet eto.

PUL OPINION:
{pool_text}

ISTOCHNIKI:
[PAMYaT]: {evidence_memory or "Pusto"}
[WEB]: {evidence_web or "Pusto"}
[ZhURNAL DNYa]: {daily_report}
""".strip()

        synth_messages = [{"role": "system", "content": truncate_text(synth_system, MAX_SYNTH_PROMPT_CHARS)}]
        synth_messages.extend(safe_history[-20:])
        synth_messages.append({"role": "user", "content": truncate_text(user_text, 20000)})

        final = await _safe_chat(synth, synth_messages, temperature=0.6, max_tokens=MAX_OUT_TOKENS, chat_id=chat_id)
        return clean_ester_response(final)'''

def apply_p2p_upgrade():
    print(f"🚀 Vzhivlenie sistemy 'Sovet Sester' v {TARGET_FILE}...")
    
    if not os.path.exists(TARGET_FILE):
        print("❌ Oshibka: Fayl ne nayden!")
        return

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # We are looking for the old function syntnesyze_thught
    # We find it from the declaration to the next function or the end of the class
    pattern = r'async\s+def\s+synthesize_thought\(.*?\)\s*->\s*str:.*?hive\s*=\s*EsterHiveMind\(\)'
    
    # We are trying to replace the main block of logic inside a function
    start_marker = "async def synthesize_thought("
    end_marker = "hive = EsterHiveMind()"
    
    if start_marker in content and end_marker in content:
        print("🧠 Struktura mozga opoznana. Nachinayu neyroplastiku...")
        
        # Finding everything between the start of the function and the next global object
        parts = content.split(start_marker)
        pre_func = parts[0]
        post_func = parts[1].split(end_marker, 1)[1]
        
        new_content = pre_func + NEW_SYNTHESIZE_THOUGHT + "\n\nhive = EsterHiveMind()" + post_func
        
        with open(TARGET_FILE, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("✅ Sistema 'Soviet Sister' uspeshno integrated.")
    else:
        print("❌ Could not find entry point for brain update.")

if __name__ == "__main__":
    apply_p2p_upgrade()