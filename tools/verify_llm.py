from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
def main():
    import os
    os.environ.setdefault("ESTER_LLM_FALLBACK","1")
    from modules.llm import broker
    print("has chat:", hasattr(broker, "chat"))
    print("has complete:", hasattr(broker, "complete"))
    print("ping:", broker.ping() if hasattr(broker,"ping") else None)
    out = broker.chat([{"role":"user","content":"ping?"}])
    print("chat.ok:", out.get("ok"), "model:", out.get("model"))
if __name__ == "__main__":
    main()