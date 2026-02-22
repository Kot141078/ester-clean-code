# -*- coding: utf-8 -*-
import os
import json
import time
import requests
from modules.perception.extractors import extract_text
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Ssylka na lokalnoe yadro (Sudyu)
API_URL = "http://127.0.0.1:8080/chat/message"

# Put k pamyati (dlya dublirovaniya logov, esli nuzhno)
CLEAN_MEMORY_PATH = os.path.join(os.getcwd(), "data", "passport", "clean_memory.jsonl")

def ingest_file(file_path: str, meta: dict) -> str:
    """
    1. Chitaet fayl (Extract).
    2. Otpravlyaet Sude na osmyslenie (Refine).
    3. Vozvraschaet otvet dlya polzovatelya.
    """
    filename = os.path.basename(file_path)
    print(f"[Perception] 👁️ Vizhu fayl: {filename}")

    # 1. EXTRACT
    raw_text = extract_text(file_path)
    char_count = len(raw_text)
    print(f"[Perception] 📖 Prochitano simvolov: {char_count}")

    if char_count < 50:
         return f"Fayl **{filename}** kazhetsya pustym ili nechitaemym.\nKontent: {raw_text}"

    # 2. REFINE (Myshlenie)
    # Formiruem prompt dlya Sudi
    prompt = (
        f"Ya zagruzil v tvoe soznanie fayl: '{filename}'.\n"
        f"Ego soderzhimoe (nachalo):\n"
        f"================================\n"
        f"{raw_text}\n"
        f"================================\n\n"
        f"TVOYa ZADAChA:\n"
        f"1. Izuchi etot dokument.\n"
        f"2. Esli eto kod — obyasni, chto on delaet.\n"
        f"3. Esli eto tekst — sdelay sammari (kratkuyu vyzhimku).\n"
        f"4. Sokhrani klyuchevye fakty v pamyat.\n"
        f"Otvet mne: o chem etot fayl i chem on polezen?"
    )

    try:
        # Otpravlyaem zapros yadru (ispolzuem mode='judge' dlya umnogo otveta)
        response = requests.post(API_URL, json={
            "message": prompt,
            "sid": "ingest_pipeline", # Spetsialnaya sessiya
            "mode": "judge",
            "author": "SystemIngest"
        }, timeout=21600) # Tvoy novyy taymaut

        if response.status_code == 200:
            data = response.json()
            analysis = data.get("reply", "Sudya promolchal.")
            provider = data.get("provider", "unknown")
            
            # 3. SAVE EXPERIENCE (Yavnoe sokhranenie fakta chteniya)
            _save_experience(filename, analysis, meta)
            
            return f"📂 **Fayl prochitan** ({char_count} simv.)\n🧠 Obrabotano: {provider}\n\n{analysis}"
        else:
            return f"❌ Oshibka yadra pri analize: {response.status_code}"

    except Exception as e:
        return f"❌ Kriticheskaya oshibka payplayna: {e}"

def _save_experience(filename, analysis, meta):
    """Pishet fakt 'Osmysleniya fayla' v chistuyu pamyat."""
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