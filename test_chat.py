# -*- coding: utf-8 -*-
import requests
import json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

url = "http://localhost:8090/chat/message"

# Varianty klyuchey, kotorye my proverim
keys_to_try = ["text", "message", "query", "prompt", "input"]

payload_value = "Privet, eto test svyazi."

print(f"--- Testirovanie API: {url} ---")

for key in keys_to_try:
    print(f"\n[?] Probuem klyuch '{key}'...")
    data = {
        key: payload_value,
        "mode": "judge",
        "sid": "python_test"
    }
    
    try:
        resp = requests.post(url, json=data)
        # Pytaemsya poluchit JSON, dazhe esli status ne 200
        try:
            res_json = resp.json()
        except:
            res_json = resp.text
            
        print(f"    Status: {resp.status_code}")
        print(f"    Otvet:  {res_json}")
        
        # Esli net oshibki no_message, znachit ugadali
        if isinstance(res_json, dict) and res_json.get("error") != "no_message":
            print(f"✅ USPEKh! Pravilnyy klyuch: '{key}'")
            break
            
    except Exception as e:
        print(f"    Oshibka soedineniya: {e}")