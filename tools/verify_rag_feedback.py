from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    # 1) Poluchim otvet ot RAG (cherez sovmestimyy ekshen)
    try:
        from modules.thinking import compat_actions as ca
        q = "Kto takaya Ester i chto ona delaet?"
        res = ca.rag_answer(q)
        text = (res.get("text") or "").strip()
    except Exception:
        q = "Chto takoe RAG?"
        text = "lokalnyy otvet: RAG — poisk po fragmentam i kratkaya vyzhimka."
    # 2) Logiruem
    from modules.rag import feedback as fb
    ev = fb.log(q, text, sources=[{"id":"doc_demo","text":"demo source"}])
    print("log.ok:", ev.get("ok"), "kg:", ev.get("kg"))
    # 3) Khvost
    tail = fb.tail(5)
    print("tail.count:", tail.get("count"))
    for it in tail.get("items", []):
        print("-", (it.get("q") or "")[:40], "=>", (it.get("text") or "")[:40])
if __name__ == "__main__":
    main()