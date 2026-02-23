# -*- coding: utf-8 -*-
import os, json, datetime as dt, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = os.getenv("ESTER_API_BASE","http://127.0.0.1:8080").rstrip("/")
MODE = os.getenv("ESTER_MODE","judge")
USE_RAG = os.getenv("ESTER_USE_RAG","1")=="1"

def post(path, body, timeout=60):
    url = f"{BASE}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8"))

def main():
    today = dt.datetime.now().date().isoformat()
    q = "Skazhi segodnyashnyuyu datu strogo v formate YYYY-MM-DD i nichego bolshe."
    code, j = post("/ester/chat/message", {"message": q, "mode": MODE, "use_rag": USE_RAG, "sid":"smoke:now"})
    ans = (j.get("answer") or "").strip()
    print(f"[ester] code={code} answer={ans!r} expected={today}")
    if today in ans:
        print("[ester] NOW: OK")
    else:
        print("[ester] NOW: FAIL")

if __name__ == "__main__":
    main()