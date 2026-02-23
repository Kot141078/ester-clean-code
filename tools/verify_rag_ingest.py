
# -*- coding: utf-8 -*-
import os, pathlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
def main():
    # vklyuchaem RAG ingest dlya testa tekuschego protsessa
    os.environ["ESTER_RAG_INGEST"] = "1"
    from modules.rag import hub
    hub.reset()
    from modules.media import watchers
    dirs = watchers.get_dirs()
    p = pathlib.Path(dirs["in"]) / "rag_demo.txt"
    p.write_text("begemot letaet nad gorodom", encoding="utf-8")
    print("tick:", watchers.tick(reason="rag_ingest"))
    print("status:", hub.status())
    print("search:", hub.search("begemot ptitsa"))
if __name__ == "__main__":
    main()