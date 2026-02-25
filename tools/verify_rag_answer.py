from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    from modules.rag import hub
    from modules.rag import answer as ra
    hub.reset()
    hub.add_text("Esther is an offline agent. RAG index to store texts and fragments of notes for answers.", {"lang":"ru"})
    hub.add_text("The RAG answers questions by extracting snippets of relevant documents and briefly summarizing them.", {"lang":"ru"})
    print("status:", hub.status())
    print("search:", hub.search("what is RAG and how does it respond?", k=3))
    out = ra.answer("What is RAG and how does it respond?", k=3)
    print("answer:", out.get("mode"), out.get("answer")[:200])
if __name__ == "__main__":
    main()