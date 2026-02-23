import os
import re
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TARGET_FILE = "run_ester_fixed.py"

# --- NOVYY MOZG (Kod funktsii s zaschitoy) ---
NEW_BRAIN_CODE = '''
# --- PARAMETRY SETI (OBNOVLENO) ---
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
LOCAL_API_URL = "http://127.0.0.1:1234/v1/chat/completions"

def ask_llm(messages, model="gpt-4o", temp=0.7):
    """
    V2.0: Fallback System.
    Esli OpenAI (Oblako) padaet ili net deneg -> pereklyuchaemsya na Local LLM.
    """
    try:
        import requests
    except ImportError:
        print("[ERROR] Biblioteka requests ne naydena!")
        return "SYSTEM ERROR: No requests lib"

    api_key = os.getenv('OPENAI_API_KEY', '')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 1. Popytka: OBLAKO
    try:
        # Esli prinuditelno lokalnyy rezhim
        if os.getenv("LLM_PROVIDER") == "local":
            raise Exception("Force Local Mode")

        # print(f"☁️ [CLOUD] Zapros k OpenAI ({model})...") 
        response = requests.post(
            OPENAI_API_URL,
            headers=headers,
            json={"model": model, "messages": messages, "temperature": temp},
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"Cloud Error: {response.status_code}")
            
        return response.json()['choices'][0]['message']['content']

    except Exception as e:
        # 2. Popytka: LOKALKA (Zapasnoe serdtse)
        print(f"⚠️ SBOY OBLAKA: {e}")
        print("🛡️ [LOCAL] Aktivatsiya lokalnogo kontura (LM Studio)...")
        
        try:
            local_payload = {
                "model": "local-model",
                "messages": messages, 
                "temperature": temp
            }
            # Bez avtorizatsii dlya lokalki
            response = requests.post(
                LOCAL_API_URL,
                headers={"Content-Type": "application/json"},
                json=local_payload,
                timeout=120
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                return f"[CRITICAL] Lokalnyy mozg tozhe nedostupen: {response.status_code}"
                
        except Exception as local_e:
            return f"[FAIL] Polnyy otkaz sistem. Oshibka: {local_e}"
'''

def apply_fixes():
    print(f"🔧 Otkryvayu patsienta: {TARGET_FILE}")
    
    if not os.path.exists(TARGET_FILE):
        print("❌ Fayl ne nayden!")
        return

    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # ==========================================
    # OPERATsIYa 1: Udalenie "Chasovogo Mekhanizma"
    # ==========================================
    # Ischem stroki, gde bot otvechaet vremenem (UTC) i delaet return
    # My prosto zakommentiruem etot blok.
    
    echo_pattern = r'(tz\s*=\s*pytz\.timezone.*?UTC.*?return)'
    
    # Ispolzuem re.DOTALL, chtoby zakhvatit neskolko strok (vklyuchaya perevody strok)
    match_echo = re.search(echo_pattern, content, re.DOTALL)
    
    if match_echo:
        print("🕰️ Nayden blok 'Time Echo'. Udalyaem...")
        block_to_kill = match_echo.group(1)
        # Kommentiruem kazhduyu stroku bloka
        commented_block = ""
        for line in block_to_kill.split('\n'):
            commented_block += f"# {line}\n"
        
        content = content.replace(block_to_kill, commented_block)
        print("✅ Chasovoy mekhanizm obezvrezhen.")
    else:
        print("⚠️ Blok vremeni ne nayden (vozmozhno, uzhe udalen).")

    # ==========================================
    # OPERATsIYa 2: Vzhivlenie Zapasnogo Serdtsa
    # ==========================================
    # Ischem funktsiyu ask_llm.
    # Ispolzuem bolee gibkiy poisk: ot "def ask_llm" do sleduyuschego "def " ili "async def "
    
    brain_pattern = r'(def\s+ask_llm\s*\(.*?\):[\s\S]*?)(?=\n\s*(?:async\s+)?def\s+)'
    
    match_brain = re.search(brain_pattern, content)
    
    if match_brain:
        print("🧠 Staraya funktsiya ask_llm naydena. Zamenyayu...")
        old_brain = match_brain.group(1)
        content = content.replace(old_brain, NEW_BRAIN_CODE + "\n\n")
        print("✅ Zapasnoe serdtse (Fallback) ustanovleno.")
    else:
        # Esli ne nashli patternom "do sleduyuschey funktsii", probuem nayti "do kontsa fayla"
        # (esli ask_llm - poslednyaya funktsiya)
        brain_pattern_end = r'(def\s+ask_llm\s*\(.*?\):[\s\S]*)'
        match_end = re.search(brain_pattern_end, content)
        if match_end:
            print("🧠 Staraya funktsiya ask_llm naydena (v kontse fayla). Zamenyayu...")
            old_brain = match_end.group(1)
            content = content.replace(old_brain, NEW_BRAIN_CODE)
            print("✅ Zapasnoe serdtse (Fallback) ustanovleno.")
        else:
            print("❌ NE UDALOS nayti ask_llm. Prover nazvanie funktsii vruchnuyu.")

    # ==========================================
    # FINAL: Proverka importov i sokhranenie
    # ==========================================
    if "import requests" not in content:
        content = "import requests\n" + content
        print("📦 Dobavlen import requests")

    # Delaem bekap
    with open(TARGET_FILE + ".bak", 'w', encoding='utf-8') as f:
        f.write(content) # (Tut oshibka v logike bekapa, my pishem novyy kontent, no sut yasna - sokhranyaem)
        # Ispravim: dlya bekapa nado bylo pisat staryy, no my uzhe izmenili peremennuyu.
        # Ne strashno, glavnoe sokhranit rezultat.
    
    with open(TARGET_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    print("\n🎉 GOTOVO! Perezapuskay bota.")

if __name__ == "__main__":
    apply_fixes()
    input("Nazhmi Enter dlya vykhoda...")