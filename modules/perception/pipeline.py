# -*- coding: utf-8 -*-
import os
import json
import time
import requests
from modules.perception.extractors import extract_text
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Link to local core (Judge)
API_URL = "http://127.0.0.1:8080/chat/message"

# Path to memory (for duplicating logs, if necessary)
CLEAN_MEMORY_PATH = os.path.join(os.getcwd(), "data", "passport", "clean_memory.jsonl")

def ingest_file(file_path: str, meta: dict) -> str:
    """1. Reads the file (Extract).
    2. Sends it to Suda for reflection (Refina).
    3. Returns a response for the user."""
    filename = os.path.basename(file_path)
    print(f"[Perception] 👁️ Vizhu fayl: {filename}")

    # 1. EXTRACT
    raw_text = extract_text(file_path)
    char_count = len(raw_text)
    print(f"[Perception] 📖 Prochitano simvolov: {char_count}")

    if char_count < 50:
         return f"The file **ZZF0Z** appears empty or unreadable.\nContent: ZZF1ZZ"

    # 2. REFINE (Myshlenie)
    # We create a prompt for the Judge
    prompt = (
        f"Ya zagruzil v tvoe soznanie fayl: '{filename}'.\n"
        f"Its contents (beginning):"
        f"================================\n"
        f"{raw_text}\n"
        f"================================\n\n"
        f"Your Task:"
        f"1. Study this document."
        f"2. If it's code, explain what it does."
        f"3. If this is a text, make a summary (short summary)."
        f"4. Keep key facts in your memory."
        f"Answer me: what is this file about and how is it useful?"
    )

    try:
        # Send a request to the kernel (use mode=yudzhey for a smart response)
        response = requests.post(API_URL, json={
            "message": prompt,
            "sid": "ingest_pipeline", # Special session
            "mode": "judge",
            "author": "SystemIngest"
        }, timeout=21600) # Tvoy novyy taymaut

        if response.status_code == 200:
            data = response.json()
            analysis = data.get("reply", "The judge remained silent.")
            provider = data.get("provider", "unknown")
            
            # 3. SAVE EXPERIENCE (Explicitly saving the fact of reading)
            _save_experience(filename, analysis, meta)
            
            return f"📂 **Fayl prochitan** ({char_count} simv.)\n🧠 Processed: {provider}\n\n{analysis}"
        else:
            return f"❌ Oshibka yadra pri analize: {response.status_code}"

    except Exception as e:
        return f"❌ Kriticheskaya oshibka payplayna: {e}"

def _save_experience(filename, analysis, meta):
    """Writes the fact of Understanding the file to clean memory."""
    entry = {
        "ts": int(time.time()),
        "type": "experience_ingest",
        "filename": filename,
        "summary": analysis,
        "meta": meta
    }
    try:
        with open(CLEAN_MEMORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"[Perception] 💾 Zapisano v opyt: {filename}")
    except Exception as e:
        print(f"[Perception] ⚠️ Oshibka zapisi pamyati: {e}")