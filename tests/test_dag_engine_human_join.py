# -*- coding: utf-8 -*-
import os
import tempfile
import time

from modules.graph.dag_engine import DAGEngine, load_context, load_plan_from_text, load_state
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PLAN = """\
run_id: test_run_human_join_01
branch_id: main
context_init:
  spec: "Verka fanout -> human.review -> script -> join."
  items:
    - {file: "a.txt"}
    - {file: "b.txt"}

nodes:
  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: []

  - id: human_check
    type: human.review
    message: "Prover {{ctx.item.file}}. Answer: OK/pravki."
    out: "approved"
    depends: ["fork"]

  - id: finalize
    type: script
    update:
      final_branch: "FINAL {{ctx.item.file}} / {{ctx.approval}}"
    depends: ["human_check"]

  - id: gather
    type:join
    from: "fork"
    out: "joined"
    select:
      file: "{{item.file}}"
      approval: "{{ctx.approval}}"
      final: "{{ctx.final_branch}}"
    mode: list
    await_nodes: ["finalize"]
    depends: ["finalize"]"""


def test_human_then_join():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        # Disables any external LLMs
        os.environ["LLM_API_BASE"] = ""
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN))

        # 1) keep the ticker cool until human tasks appear
        for _ in range(200):
            eng.tick()
            st = load_state(eng.run_id)
            infl = st.get("inflight") or {}
            if infl:
                break
            time.sleep(0.01)
        assert load_state(eng.run_id).get("inflight") or {}, "inflight ne poyavilsya"

        # 2) we answer as a “person” for all tasks
        inflight = list((load_state(eng.run_id).get("inflight") or {}).keys())
        for tid in inflight:
            ok = eng.on_human_completed(tid, {"result": "OK"})
            assert ok is True

        # 3) screw it to completion
        for _ in range(500):
            if load_state(eng.run_id).get("finished"):
                break
            eng.tick()
            time.sleep(0.005)

        st_fin = load_state(eng.run_id)
        assert st_fin.get("finished") is True

        # 4) check that ein collected the results from two branches
        main_ctx = load_context(eng.run_id, "main")
        joined = main_ctx.get("joined")
        assert isinstance(joined, list) and len(joined) == 2
        files = sorted([row.get("file") for row in joined])
        assert files == ["a.txt", "b.txt"]
        # Let's check that the approval and final are present
        for row in joined:
            assert row.get("approval") == "OK"
            assert "FINAL" in (row.get("final") or "")
