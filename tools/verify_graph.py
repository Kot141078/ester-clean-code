from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def main():
    from modules.graph import kg_nodes as kg
    print("add_entity:", kg.add_entity("ester", ["Agent"], {"ver": "0.1"}))
    print("add_relation:", kg.add_relation("ester", "uses", "lmstudio", {"proto": "openai"}))
    print("query Agent:", kg.query("Agent"))
if __name__ == "__main__":
    main()