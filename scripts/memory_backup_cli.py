# -*- coding: utf-8 -*-
"""
scripts/memory_backup_cli.py — CLI dlya bekapov pamyati Ester.

Primery:
  python scripts/memory_backup_cli.py create "pre-upgrade"
  python scripts/memory_backup_cli.py list
  python scripts/memory_backup_cli.py verify bk-20250101-120000
  python scripts/memory_backup_cli.py restore bk-... replace
  python scripts/memory_backup_cli.py purge 20 90

# c=a+b
"""
import sys
from modules.memory import backups
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def main(argv):
    if len(argv)<2:
        print("usage: create [label] | list | verify <id> | restore <id> [replace|merge] | purge [keep] [age_days]")
        return 1
    cmd = argv[1]
    if cmd == "create":
        label = argv[2] if len(argv)>2 else None
        print(backups.create_backup(label))
    elif cmd == "list":
        print(backups.list_backups())
    elif cmd == "verify":
        print(backups.verify_backup(argv[2]))
    elif cmd == "restore":
        bid = argv[2]; mode = argv[3] if len(argv)>3 else "replace"
        print(backups.restore_backup(bid, mode))
    elif cmd == "purge":
        keep = int(argv[2]) if len(argv)>2 else 20
        age  = int(argv[3]) if len(argv)>3 else 90
        print(backups.purge_old(keep, age))
    else:
        print("unknown command")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))