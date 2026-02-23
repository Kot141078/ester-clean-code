from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
def main():
    from importlib import import_module
    r = import_module("modules.act.runner")
    print("has run_plan:", hasattr(r, "run_plan"))
    if hasattr(r, "run_plan"):
        print("call run_plan:", r.run_plan({"name":"smoke"}))

if __name__ == "__main__":
    main()