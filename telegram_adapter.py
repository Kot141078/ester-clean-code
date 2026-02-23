# -*- coding: utf-8 -*-
import time
import requests
import traceback
import os
import threading
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Nastroyki
API_URL = "http://127.0.0.1:8080/chat/message"
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def listen():
    if not TG_TOKEN:
        print("[TG] No token found")
        return
    
    offset = 0
    print(f"[TG] Listening... (telegram token configured: {'yes' if bool(TG_TOKEN) else 'no'})")
    
    while True:
        try:
            # Long polling
            url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates?offset={offset}&timeout=30"
            r = requests.get(url, timeout=40)
            data = r.json()
            
            if not data.get("ok"):
                time.sleep(5)
                continue
                
            for result in data.get("result", []):
                offset = result["update_id"] + 1
                msg = result.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                
                if not text or not chat_id:
                    continue
                
                print(f"[TG] Incoming: {text}")
                
                # Otpravlyaem Ester
                try:
                    payload = {
                        "message": text,
                        "sid": str(chat_id),
                        "mode": "judge", # Ispolzuem nashego novogo umnogo sudyu
                        "author": "TelegramUser"
                    }
                    
                    ester_resp = requests.post(API_URL, json=payload, timeout=21600)
                    if ester_resp.status_code != 200:
                        reply_text = f"Oshibka servera: {ester_resp.status_code}"
                    else:
                        rj = ester_resp.json()
                        # --- VAZhNYY MOMENT: Ischem otvet vezde ---
                        reply_text = rj.get("reply") or rj.get("answer") or rj.get("text") or "..."
                        
                        # Dobavlyaem otladku provaydera
                        prov = rj.get("provider", "unknown")
                        if prov:
                            reply_text += f"\n\n(🧠 {prov})"

                except Exception as e:
                    reply_text = f"Oshibka svyazi s Ester: {e}"
                    print(f"[TG] Error: {e}")

                # Otpravlyaem v Telegram
                send_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                requests.post(send_url, json={"chat_id": chat_id, "text": reply_text})
                
        except Exception as e:
            print(f"[TG] Loop error: {e}")
            time.sleep(5)

# Zapusk v potoke, esli importirovano kak modul
if __name__ == "__main__":
    listen()
else:
    # Esli zagruzhaet runner.py
    t = threading.Thread(target=listen, daemon=True)
    t.start()


