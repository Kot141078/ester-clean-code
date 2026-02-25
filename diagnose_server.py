import requests
import json
import sys
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

base = os.getenv("ESTER_CHAT_BASE") or os.getenv("ESTER_HTTP_BASE") or "http://localhost:8090"
url = base.rstrip("/") + "/chat/message"

# Test 1: The simplest request (checking for required fields)
payload_minimal = {"message": "Ping"}

# Test 2: Request with “extra” fields that can infuriate Guard
payload_full = {
    "message": "Full check",
    "sid": "debug_console",
    "mode": "cloud",
    "author": "Owner",
    "rag": False  # Often causes an error in Podantic V2
}

def run_test(name, data):
    print(f"--- {name} ---")
    try:
        r = requests.post(url, json=data, timeout=5)
        print(f"Status: {r.status_code}")
        try:
            print(f"Response: {r.json()}")
        except:
            print(f"Raw text: {r.text}")
    except Exception as e:
        print(f"Connection failed: {e}")
    print("")

if __name__ == "__main__":
    print(f"Testing URL: {url}\n")
    run_test("Minimal Payload", payload_minimal)
    run_test("Full Payload", payload_full)