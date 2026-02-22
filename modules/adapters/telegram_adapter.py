# -*- coding: utf-8 -*-
"""
modules/adapters/telegram_adapter.py - DEDUP EDITION
Slushaet Telegram, otpravlyaet v Chat API.
Vklyuchaet zaschitu ot povtornoy obrabotki (Deduplication).
"""
import os
import time
import requests
import threading
from dotenv import load_dotenv
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

load_dotenv()

TG_TOKEN = os.getenv("TG_TOKEN")
# Adres Chat API (lokalnyy)
API_URL = "http://127.0.0.1:8080/chat/message"

# Globalnaya peremennaya dlya deduplikatsii v pamyati
LAST_PROCESSED_ID = 0

def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store  # type: ignore
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass

def get_updates(offset=None):
    if not TG_TOKEN: return []
    url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates"
    params = {"timeout": 10, "offset": offset}
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json().get("result", [])
    except Exception as e:
        print(f"[TG] Poll Error: {e}")
        try:
            _mirror_background_event(
                f"[TG_ADAPTER_POLL_ERROR] {e}",
                "telegram_adapter",
                "poll_error",
            )
        except Exception:
            pass
    return []

def send_message(chat_id, text):
    if not TG_TOKEN: return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def process_message(msg):
    global LAST_PROCESSED_ID
    
    update_id = msg.get("update_id")
    message = msg.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    user_name = message.get("from", {}).get("first_name", "User")
    
    if not text or not chat_id: return update_id

    # === DEDUP CHECK ===
    # Esli my (ili drugoy potok/skript) uzhe obrabotali etot ID -> propuskaem
    if update_id <= LAST_PROCESSED_ID:
        return update_id

    print(f"[TG] Processing ID {update_id}: {text[:30]}...")
    try:
        _mirror_background_event(
            f"[TG_ADAPTER_IN] id={update_id} text={text[:120]}",
            "telegram_adapter",
            "inbound",
        )
    except Exception:
        pass
    
    # Otpravka v Chat API
    try:
        # Marker dlya ChatAPI, chto eto soobschenie iz Telegram
        payload = {"message": text, "user": user_name, "source": "telegram"}
        r = requests.post(API_URL, json=payload, timeout=600)
        
        if r.status_code == 200:
            data = r.json()
            reply = data.get("reply", "...")
            provider = data.get("provider", "unknown")
            
            # Formatiruem podpis zdes (ODIN RAZ)
            # chat_api teper vozvraschaet chistoe imya, naprimer "lokalnaya LM Studio"
            final_text = f"{reply}\n\n(🧠 {provider})"
            
            send_message(chat_id, final_text)
            try:
                _mirror_background_event(
                    f"[TG_ADAPTER_OUT] id={update_id} provider={provider} reply={reply[:200]}",
                    "telegram_adapter",
                    "outbound",
                )
            except Exception:
                pass
        else:
            send_message(chat_id, f"⚠️ Oshibka yadra: {r.status_code}")
            try:
                _mirror_background_event(
                    f"[TG_ADAPTER_CORE_ERR] status={r.status_code}",
                    "telegram_adapter",
                    "core_error",
                )
            except Exception:
                pass
            
    except Exception as e:
        print(f"[TG] Relay Error: {e}")
        try:
            _mirror_background_event(
                f"[TG_ADAPTER_RELAY_ERROR] {e}",
                "telegram_adapter",
                "relay_error",
            )
        except Exception:
            pass
        send_message(chat_id, "⚠️ Oshibka svyazi s yadrom Ester.")

    # Obnovlyaem globalnyy ID
    LAST_PROCESSED_ID = update_id
    return update_id

def telegram_loop():
    global LAST_PROCESSED_ID
    print(f"[TG] Adapter started. Token ending: ...{TG_TOKEN[-4:] if TG_TOKEN else 'NONE'}")
    try:
        _mirror_background_event(
            "[TG_ADAPTER_START]",
            "telegram_adapter",
            "start",
        )
    except Exception:
        pass
    
    offset = 0
    while True:
        updates = get_updates(offset)
        for u in updates:
            uid = u.get("update_id")
            # Esli eto staroe soobschenie (obrabotannoe do perezagruzki), prosto sdvigaem offset
            process_message(u)
            offset = uid + 1
            LAST_PROCESSED_ID = max(LAST_PROCESSED_ID, uid)
        time.sleep(1)

# Avtozapusk pri importe (kak v tvoey arkhitekture)
# No zapuskaem v otdelnom potoke, chtoby ne blochit app.py
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or True: # Force run usually
    # Proverka, chtoby ne zapustit 10 potokov pri reloadere flaska
    # Obychno Flask zapuskaet dva protsessa (glavnyy i reloader).
    # Prosteyshaya zaschita - etot fayl dolzhen byt loaded odin raz.
    if not any(t.name == "EsterTGPoller" for t in threading.enumerate()):
        t = threading.Thread(target=telegram_loop, name="EsterTGPoller", daemon=True)
        t.start()