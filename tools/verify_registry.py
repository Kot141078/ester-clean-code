from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    from modules.registry import put, get, list_names, search, base_dir
    ns = "smoke"
    key = "item"
    print("base_dir:", base_dir())
    print("put:", put(ns, key, {"ok": True, "v": 1}))
    print("get:", get(ns, key))
    print("list:", list_names(ns))
    print("search 'it':", search(ns, "it"))
if __name__ == "__main__":
    main()