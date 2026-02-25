from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    from modules.thinking import compat_actions as ca
    print("try_register:", ca.try_register())
    q = "What is Esther?"
    print("heuristic:", ca.heuristic_should_rag(q))
    res = ca.rag_answer(q)
    print("rag_answer.ok:", res.get("ok"), "len:", len(res.get("text","")))
    print("---")
    print(res.get("text","")[:200])
if __name__ == "__main__":
    main()