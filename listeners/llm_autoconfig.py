# -*- coding: utf-8 -*-
"""listeners/llm_autoconfig.py - fonovyy avtokonfig LLM.

Behavior:
  • Kazhdye interval sek: run_once().
  • V AB=A — only plany i self-check bez izmeneniy.
  • V AB=B - esli plan predlagaet import - sozdaem modeli v Ollama (lokalnye .gguf).

ENV/CFG: sm. modules.llm.autoconfig_settings.

Mosty:
- Yavnyy (Kibernetika ↔ Orkestratsiya): avtonomnyy tsikl privedeniya LLM k “rabochemu minimumu”.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): zhurnal sostoyaniya na diske; otsutstvie vneshney seti.
- Skrytyy 2 (Praktika ↔ Sovmestimost): drop-in; uvazhenie AB-rezhima.

Zemnoy abzats:
This is “naladchik”: periodicheski proveryaet, khvataet li dvizhku modeley, i pri neobkhodimosti dozavozit iz lokalnykh faylov.

# c=a+b"""
from __future__ import annotations

import argparse, time
from modules.llm.autoconfig_settings import load_llm_settings  # type: ignore
from modules.llm.autoconfig import run_once  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester LLM autoconfig listener")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=0)
    args = ap.parse_args(argv)

    cfg = load_llm_settings()
    if not cfg.get("enable"):
        print("[llm-autoconfig] disabled", flush=True)
        return 0

    interval = int(args.interval or cfg.get("interval", 900))

    try:
        while True:
            rep = run_once(cfg)
            print(str(rep)[:1000], flush=True)
            if not args.loop:
                break
            time.sleep(max(60, interval))
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# c=a+b