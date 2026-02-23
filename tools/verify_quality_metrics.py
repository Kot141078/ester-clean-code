# -*- coding: utf-8 -*-
import time, random
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
def main():
    from modules.quality import guard
    print("enable:", guard.enable())
    # sintetika: 20 uspeshnykh, 5 oshibok, raznye zaderzhki
    for _ in range(20):
        guard.record_latency(True, random.uniform(50, 250))
    for _ in range(5):
        guard.record_latency(False, random.uniform(100, 800))
    print("status:", guard.status())
    print("decide:", guard.decide())
if __name__ == "__main__":
    main()