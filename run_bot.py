# -*- coding: utf-8 -*-
import sys
import os

# Adding the path to the modules
sys.path.append(os.path.join(os.getcwd(), "modules"))

from modules.telegram_client import listen
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

print("=== LAUNCHING THE INDEPENDENT TELEGRAM MODULE (EARC) ===")
print("Waiting for kernel server at http://127.0.0.1:8090...")

if __name__ == "__main__":
    try:
        listen()
    except KeyboardInterrupt:
        print("\n[Bot] Ostanovlen polzovatelem.")