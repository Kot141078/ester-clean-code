# -*- coding: utf-8 -*-
import sys, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
def main():
    payload = json.loads(sys.stdin.read())
    cfg = payload.get("config", {})
    t = float(cfg.get("llm", {}).get("temperature", 0.5))
    rag_k = int(cfg.get("rag", {}).get("k", 4))
    jmode = str(cfg.get("judge", {}).get("mode", "majority"))
    utility = 1.0 - abs(t - 0.3)
    accuracy = 0.6 + 0.1 * (rag_k >= 3) + (0.1 if jmode == "consensus" else 0.0)
    time_sec = 0.3 + 0.05 * rag_k
    err_rate = 0.05 + abs(t - 0.3) * 0.2
    out = {
        "utility": max(0.0, min(1.0, utility)),
        "accuracy": max(0.0, min(1.0, accuracy)),
        "time_sec": max(0.01, time_sec),
        "err_rate": max(0.0, min(1.0, err_rate)),
        "tokens_prompt": 128,
        "tokens_gen": 256
    }
    print(json.dumps(out, ensure_ascii=False))
if __name__ == "__main__":
    main()