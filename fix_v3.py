import os
import re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET_FILE = "run_ester_fixed.py"

# --- NOVAYa FUNKTsIYa MOZGA (S ZASchITOY) ---
# My zamenyaem _safe_chat na versiyu, kotoraya umeet pereklyuchatsya na Local pri oshibkakh.
NEW_SAFE_CHAT_CODE = '''async def _safe_chat(
    provider: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = MAX_OUT_TOKENS,
    chat_id: Optional[int] = None,
) -> str:
    # --- FALLBACK LOGIC INJECTED BY FIX_V3 ---
    # Vnutrennyaya funktsiya popytki zaprosa
    async def _try_request(prov_name, msgs, temp, max_tok):
        client = PROVIDERS.client(prov_name)
        cfg = PROVIDERS.cfg(prov_name)
        
        # Khard-kap tokenov iz konfiga
        hard_cap = int(getattr(cfg, "max_out_tokens", 0) or 0)
        start_max = int(max_tok)
        if hard_cap > 0:
            start_max = min(start_max, hard_cap)

        # Lestnitsa tokenov (Step-down) dlya borby s perepolneniem konteksta
        base_steps = [start_max, 12000, 8192, 8000, 6000, 4000, 2000, 1000, 512, 256, 128]
        token_steps = []
        seen = set()
        for mt in base_steps:
            if mt <= 0 or mt > start_max or mt in seen: continue
            seen.add(mt)
            token_steps.append(mt)
        
        last_error = None
        for mt in token_steps:
            try:
                resp = await client.chat.completions.create(
                    model=cfg.model,
                    messages=msgs,
                    temperature=temp,
                    max_tokens=mt,
                )
                txt = (resp.choices[0].message.content or "").strip()
                if txt: return txt
            except Exception as e:
                last_error = e
                # Esli oshibka konteksta - probuem menshe tokenov
                err_str = str(e).lower()
                if any(x in err_str for x in ["context", "max", "token", "length", "bad request"]):
                    continue
                # Esli oshibka seti/deneg (429) - vykhodim srazu, chtoby srabotal Fallback
                raise e
        if last_error: raise last_error
        return ""

    # 1. Normalizatsiya soobscheniy
    norm_messages = _normalize_messages_for_provider(provider, messages, chat_id=chat_id)
    
    # 2. Osnovnaya popytka
    try:
        return await _try_request(provider, norm_messages, temperature, max_tokens)
    except Exception as e:
        # 3. AVARIYNYY REZhIM (FALLBACK)
        # Esli my esche ne na lokalke - pereklyuchaemsya
        if provider != "local":
            logging.warning(f"⚠️ [BRAIN] Oblako ({provider}) upalo: {e}. Perekhozhu na LOCAL...")
            try:
                # Probuem lokalnyy mozg
                return await _try_request("local", norm_messages, temperature, max_tokens)
            except Exception as local_e:
                logging.error(f"❌ [BRAIN] Lokalnyy mozg tozhe ne otvetil: {local_e}")
                return ""
        
        logging.error(f"❌ [BRAIN] Oshibka provaydera {provider}: {e}")
        return ""
'''

def apply_fixes():
    print(f"🔧 Otkryvayu patsienta: {TARGET_FILE}")
    
    if not os.path.exists(TARGET_FILE):
        print(f"❌ Fayl {TARGET_FILE} ne nayden!")
        return

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # ==========================================
    # OPERATsIYa 1: Ubiystvo "Kukushki" (Time Echo)
    # ==========================================
    # Ischem spisok time_triggers = [...]
    # Ispolzuem regex, kotoryy zakhvatyvaet kvadratnye skobki i vse vnutri
    trigger_pattern = r'time_triggers\s*=\s*\[.*?\]'
    
    match_trigger = re.search(trigger_pattern, content, re.DOTALL)
    
    if match_trigger:
        print("🕰️ Nashel triggery vremeni. Ochischayu...")
        # Zamenyaem ves spisok na pustoy
        content = content.replace(match_trigger.group(0), 'time_triggers = [] # Ochischeno fix_v3 (Disable Time Echo)')
        print("✅ Reaktsiya na slovo 'segodnya' otklyuchena.")
    else:
        print("⚠️ Spisok triggerov ne nayden (vozmozhno, uzhe ochischen).")

    # ==========================================
    # OPERATsIYa 2: Vzhivlenie Fallback (_safe_chat)
    # ==========================================
    # Ischem funktsiyu async def _safe_chat(...): ... do sleduyuschey funktsii async def need_web_search_llm
    
    # Regulyarka: ischem ot nachala _safe_chat do nachala sleduyuschey funktsii
    brain_pattern = r'(async\s+def\s+_safe_chat\(.*?\):[\s\S]*?)(?=\nasync\s+def\s+need_web_search_llm)'
    
    match_brain = re.search(brain_pattern, content)
    
    if match_brain:
        print("🧠 Funktsiya _safe_chat naydena. Zamenyayu na broneboynuyu versiyu...")
        old_code = match_brain.group(1)
        content = content.replace(old_code, NEW_SAFE_CHAT_CODE)
        print("✅ Zapasnoe serdtse (Fallback -> Local) ustanovleno.")
    else:
        print("❌ Ne udalos nayti granitsy funktsii _safe_chat. Prover fayl vruchnuyu.")
        # Popytka nayti khotya by nachalo, esli konets ne sovpal
        if "async def _safe_chat" in content:
            print("   -> Funktsiya suschestvuet, no regulyarka ne sovpala s kontsom.")

    # Sokhranyaem
    with open(TARGET_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    print("\n🎉 GOTOVO! Perezapuskay bota.")

if __name__ == "__main__":
    apply_fixes()
    input("Nazhmi Enter dlya vykhoda...")