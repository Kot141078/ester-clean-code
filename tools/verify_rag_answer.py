from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    from modules.rag import hub
    from modules.rag import answer as ra
    hub.reset()
    hub.add_text("Ester — offlayn-agent. RAG indeks khranit teksty i fragmenty zametok dlya otvetov.", {"lang":"ru"})
    hub.add_text("RAG otvechaet na voprosy, izvlekaya fragmenty relevantnykh dokumentov i kratko rezyumiruya.", {"lang":"ru"})
    print("status:", hub.status())
    print("search:", hub.search("chto takoe RAG i kak on otvechaet", k=3))
    out = ra.answer("chto takoe RAG i kak on otvechaet?", k=3)
    print("answer:", out.get("mode"), out.get("answer")[:200])
if __name__ == "__main__":
    main()