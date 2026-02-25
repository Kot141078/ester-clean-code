from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def _hub_add(text, meta=None):
    try:
        from modules.rag import hub
        fn = getattr(hub, "add", None) or getattr(hub, "upsert", None) or getattr(hub, "put", None)
        if callable(fn):
            return fn(text, meta or {})
    except Exception:
        pass
    return {"ok": False}

def main():
    # 0) sidiruem 2-3 dokumenta
    _hub_add("Esther is an offline agent. It uses the local RAG index for responses.", {"lang":"ru"})
    _hub_add("The RAG answers questions by extracting fragments of relevant documents.", {"lang":"ru"})
    _hub_add("The system stores notes and snippets for offline Q&A.", {"lang":"en"})

    # 1) sobiraem malenkiy dataset
    import os, json
    path = os.path.join("data","rag_eval","demo.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    examples = [
        {"q": "Kto takaya Ester?", "gold": ["Ester — offlayn-agent."]},
        {"q": "How does the RAG prepare a response?", "gold": ["extracting fragments of relevant documents"]},
    ]
    with open(path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\\n")

    # 2) start the assessment
    from modules.rag import eval as ev
    rep = ev.run_file(path, k=3)
    print("report.ok:", rep.get("ok"), "n:", rep.get("n"), "hit@k:", rep.get("hit@k"))
    print("rows:", len(rep.get("rows") or []))
if __name__ == "__main__":
    main()