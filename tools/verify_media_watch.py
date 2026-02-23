from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
def main():
    import os, pathlib, time
    from modules.media import watchers, progress
    # Podgotovka
    dirs = watchers.get_dirs()
    in_dir = pathlib.Path(dirs["in"])
    # sozdaem testovyy fayl
    p = in_dir / "demo.txt"
    if not p.exists():
        p.write_text("hello ester", encoding="utf-8")
    print("tick:", watchers.tick(reason="verify"))
    print("summary:", progress.summary())
if __name__ == "__main__":
    main()