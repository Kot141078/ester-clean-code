from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    from modules.reports import export_http as ex
    items = ex._collect()
    print("keys:", sorted(list(items.keys())))
    tgz = ex._make_tgz(items)
    print("tgz_size:", len(tgz), "bytes")
    print("manifest.ok:", "manifest.json" in items)
if __name__ == "__main__":
    main()