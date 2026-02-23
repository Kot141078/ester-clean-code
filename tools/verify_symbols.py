from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
"""
tools.verify_symbols — proverka mostov memory/quality.
Zapusk: python -m tools.verify_symbols
# c=a+b
"""
def _try(name, fn):
    try:
        out = fn()
        print(f"[OK] {name}: {out!r}")
    except Exception as e:
        print(f"[ERR] {name}: {e}")

def main():
    _try("import memory.decay_gc", lambda: __import__("memory.decay_gc"))
    _try("from memory import decay_gc; getattr(run?)",
         lambda: hasattr(__import__("memory.decay_gc", fromlist=['run']), "run"))
    _try("from modules.quality.guard import enable", lambda: (__import__("modules.quality.guard", fromlist=['enable']).enable()))
    _try("quality.guard.status", lambda: (__import__("quality.guard", fromlist=['status']).status()))

if __name__ == "__main__":
    main()