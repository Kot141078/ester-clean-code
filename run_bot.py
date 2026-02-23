# -*- coding: utf-8 -*-
import sys
import os

# Dobavlyaem put k modulyam
sys.path.append(os.path.join(os.getcwd(), "modules"))

from modules.telegram_client import listen
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

print("=== ZAPUSK NEZAVISIMOGO MODULYa TELEGRAM (EARS) ===")
print("Ozhidanie servera yadra na http://127.0.0.1:8090...")

if __name__ == "__main__":
    try:
        listen()
    except KeyboardInterrupt:
        print("\n[Bot] Ostanovlen polzovatelem.")