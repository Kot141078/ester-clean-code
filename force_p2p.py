import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET_FILE = "run_ester_fixed.py"

def force_upgrade():
    if not os.path.exists(TARGET_FILE):
        print("❌ Fayl ne nayden!")
        return

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    skip = False
    injected = False

    for line in lines:
        # Finding the beginning of the old function
        if "async def synthesize_thought" in line:
            skip = True
            if not injected:
                # Inserting a new version of the function with P2P
                new_lines.append("    async def synthesize_thought(self, user_text: str, safe_history: List[Dict[str, Any]], base_system_prompt: str, identity_prompt: str, people_context: str, evidence_memory: str, file_context: str, facts_str: str, daily_report: str, chat_id: int = None) -> str:\n")
                new_lines.append("        synth = self.pick_reply_synth()\n")
                new_lines.append("        logging.info(f'[HIVE] P2P Synapse Active. Judge: {synth}')\n")
                new_lines.append("        sister_task = asyncio.create_task(ask_sister_opinion(user_text))\n")
                new_lines.append("        opinion_tasks = []\n")
                new_lines.append("        for p in self.active:\n")
                new_lines.append("            msgs = [{'role': 'system', 'content': base_system_prompt}, {'role': 'user', 'content': user_text}]\n")
                new_lines.append("            opinion_tasks.append(self._ask_provider(p, msgs))\n")
                new_lines.append("        opinions_raw = await asyncio.gather(*opinion_tasks, return_exceptions=True)\n")
                new_lines.append("        sister_opinion = await sister_task\n")
                new_lines.append("        pool = '\\n'.join([f'=== MNENIE {r.get(\"provider\")} ===\\n{r.get(\"text\")}' for r in opinions_raw if not isinstance(r, Exception)])\n")
                new_lines.append("        if sister_opinion: pool += f'\\n=== MNENIE SESTRY ===\\n{sister_opinion}'\n")
                new_lines.append("final_prompt = yu{role: system, unkontent: fZZF0TSZENSYNTHESIS THE TOTAL TAKEN INTO SISTER’S OPINION: encZF1ZZ}, ZZF2ZZsch")
                new_lines.append("        final = await _safe_chat(synth, final_prompt)\n")
                new_lines.append("        return clean_ester_response(final)\n")
                injected = True
            continue
        
        # Finding the end of the function (next def)
        if skip and ("async def" in line or "def " in line) and "synthesize_thought" not in line:
            skip = False
        
        if not skip:
            new_lines.append(line)

    with open(TARGET_FILE, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("✅ MOZG PEREPROSHIT. Now P2P neizbezhen.")

force_upgrade()