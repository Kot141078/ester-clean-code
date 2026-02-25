# -*- coding: utf-8 -*-
import requests
import json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

url = "http://localhost:8090/chat/message"

# Key options we will check
keys_to_try = ["text", "message", "query", "prompt", "input"]

payload_value = "Hello, this is a communication test."

print(f"--- Testirovanie API: {url} ---")

for key in keys_to_try:
    print(f"y?sh Let's try the key ъЗЗФ0ЗЗ...")
    data = {
        key: payload_value,
        "mode": "judge",
        "sid": "python_test"
    }
    
    try:
        resp = requests.post(url, json=data)
        # We are trying to get ZhSON, even if the status is not 200
        try:
            res_json = resp.json()
        except:
            res_json = resp.text
            
        print(f"    Status: {resp.status_code}")
        print(f"    Otvet:  {res_json}")
        
        # If there is no error no_message, then you guessed right
        if isinstance(res_json, dict) and res_json.get("error") != "no_message":
            print(f"✅USPEKh! Correctly klyuch: '{key}'")
            break
            
    except Exception as e:
        print(f"Connection error: ZZF0Z")