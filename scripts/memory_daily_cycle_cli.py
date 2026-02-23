# -*- coding: utf-8 -*-
"""
scripts/memory_daily_cycle_cli.py — CLI dlya sutochnogo tsikla pamyati.

Primery:
  python scripts/memory_daily_cycle_cli.py run
  python scripts/memory_daily_cycle_cli.py status
  python scripts/memory_daily_cycle_cli.py start
  python scripts/memory_daily_cycle_cli.py stop

# c=a+b
"""
import sys
from modules.memory import daily_cycle
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv):
    if len(argv)<2:
        print("usage: run|status|start|stop"); return 1
    cmd=argv[1]
    if cmd=="run":
        print(daily_cycle.run_cycle(manual=True))
    elif cmd=="status":
        print(daily_cycle.status())
    elif cmd=="start":
        print(daily_cycle.start_scheduler())
    elif cmd=="stop":
        print(daily_cycle.stop_scheduler())
    else:
        print("unknown"); return 1
    return 0

if __name__=="__main__":
    raise SystemExit(main(sys.argv))