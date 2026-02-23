from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
def main():
    from modules.graph.dag_kg_bridge import build_graph_for_entity, run_graph
    spec = build_graph_for_entity("ester_dag", ["Agent"], {"ver":"0.3"},
                                  relations=[("ester_dag","uses","lmstudio",{"proto":"openai"})])
    out = run_graph(spec)
    print("dag.run:", out)
if __name__ == "__main__":
    main()