from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
"""
tools/verify_imports.py — bystryy smoke dlya kritichnykh importov.
Zapusk:  python -m tools.verify_imports
# c=a+b
"""
def _try(it):
    name, fn = it
    try:
        fn()
        print(f"[OK] {name}")
    except Exception as e:
        print(f"[ERR] {name}: {e}")

def main():
    tests = []
    tests.append(("from modules import telegram_feed_store",
                  lambda: (__import__("modules").telegram_feed_store)))
    tests.append(("from modules.agents import task_tutor",
                  lambda: (__import__("modules.agents", fromlist=['task_tutor']).task_tutor)))
    tests.append(("import modules.listeners",
                  lambda: __import__("modules.listeners")))
    tests.append(("import modules.messaging",
                  lambda: __import__("modules.messaging")))
    tests.append(("from modules.llm import autoconfig_settings",
                  lambda: __import__("modules.llm.autoconfig_settings")))
    tests.append(("from modules.subconscious import engine",
                  lambda: (__import__("modules.subconscious", fromlist=['engine']).engine)))
    tests.append(("from modules.graph import dag_engine",
                  lambda: (__import__("modules.graph", fromlist=['dag_engine']).dag_engine)))
    tests.append(("from modules.selfcheck import run",
                  lambda: (__import__('modules.selfcheck', fromlist=['run']).run)))
    for it in tests:
        _try(it)
    print("done.")

if __name__ == "__main__":
    main()