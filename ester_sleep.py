# -*- coding: utf-8 -*-
import os
import json
import datetime
import logging
import requests
from dotenv import load_dotenv
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Nastroyka putey
BASE_DIR = r"D:\ester-project"
MEMORY_FILE = os.path.join(BASE_DIR, "data", "passport", "clean_memory.jsonl")
LOG_DIR = os.path.join(BASE_DIR, "data", "logs")

# Load the config (to know the LLM address)
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Nastroyki LLM
LLM_API_URL = os.getenv("LLM_API_BASE", "http://localhost:1234/v1") + "/chat/completions"
LLM_API_KEY = os.getenv("LLM_API_KEY", "lm-studio")
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "local-model")

def setup_logging():
    """Sets up logging and returns handlers to monitor resources."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("EsterSleep")
    logger.setLevel(logging.INFO)
    
    # To avoid duplicating logs during repeated launches
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - [SLEEP] - %(message)s")
    
    # File Handler
    log_path = os.path.join(LOG_DIR, "sleep_cycles.log")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(formatter)
    
    # Stream Handler
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger, fh

logger, file_handler = setup_logging()

def get_todays_memories():
    """Reads the profile and returns events for the last 24 hours."""
    if not os.path.exists(MEMORY_FILE):
        logger.warning("Memory file not found!")
        return []

    memories = []
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(hours=24)

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    ts_str = rec.get("timestamp")
                    if not ts_str:
                        continue
                    
                    try:
                        ts = datetime.datetime.fromisoformat(ts_str)
                    except ValueError:
                        continue

                    # Reducing to naive for comparison
                    if ts.tzinfo and cutoff.tzinfo is None:
                         ts = ts.replace(tzinfo=None)
                    
                    if ts > cutoff:
                        if "role_user" in rec:
                            memories.append(f"Owner: {rec['role_user']}")
                        elif "role_assistant" in rec:
                            memories.append(f"Ester: {rec['role_assistant']}")
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error(f"Error reading memory: {e}")
    
    return memories

def dream(context_text):
    """Sends a request to the subconscious (LLM)."""
    if not context_text:
        return None

    logger.info("Entering REM sleep (Dreaming)...")
    
    system_prompt = (
        "You are Esther's subconscious. Your task is memory consolidation."
        "Proanaliziruy dialogi za proshedshiy den.\n"
        "NE pereskazyvay ikh.\n"
        "Vydeli GLAVNYE INSAYTY:\n"
        "1. What have we learned new about Ovner (character, facts)?"
        "2. How has our relationship changed?"
        "3. What lesson have we learned?"
        "The answer should be short (2-3 sentences), in the first person (I)."
        "Begin your answer with the phrase:"
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Events of the day:\nZZF0Z"}
        ],
        "temperature": 0.6,
        "max_tokens": 500
    }

    try:
        resp = requests.post(LLM_API_URL, json=payload, headers={"Authorization": f"Bearer {LLM_API_KEY}"}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Dream failed: {e}")
        return None

def save_reflection(text):
    """Zapisyvaet insayt v profile."""
    if not text:
        return

    try:
        ts = datetime.datetime.now().isoformat()
        rec = {
            "timestamp": ts,
            "role_system": text,
            "tags": ["reflection", "nightly", "consolidation"]
        }
        
        with open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            
        logger.info(f"Insight crystallized: {text[:50]}...")
    except Exception as e:
        logger.error(f"Failed to save reflection: {e}")

def main():
    logger.info("--- Starting Nightly Consolidation Cycle ---")
    try:
        # 1. Sbor dannykh
        memories = get_todays_memories()
        if not memories:
            logger.info("No memories found for today. Nothing to consolidate.")
            return

        logger.info(f"Found {len(memories)} interaction blocks from today.")
        context = "\n".join(memories)

        # 2. Son (Obrabotka)
        insight = dream(context)

        # 3. Awakening (Recording)
        if insight:
            save_reflection(insight)
            logger.info("--- Sleep Cycle Complete. Good morning, Owner. ---")
        else:
            logger.warning("Sleep produced no dreams.")
    finally:
        # Explicitly closing the log file handler to prevent ResourceWarning
        file_handler.close()

if __name__ == "__main__":
    main()
