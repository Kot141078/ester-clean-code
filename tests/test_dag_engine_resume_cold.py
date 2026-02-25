# -*- coding: utf-8 -*-
import os
import tempfile
import time

from modules.graph.dag_engine import (
    DAGEngine,
    load_context,
    load_plan_from_text,
    load_state,
    run_loop,
)

PLAN = """\
run_id: test_run_resume_cold_01
branch_id: main
context_init:
  spec: "Proverka vozobnovleniya: human.review + kholodnyy dvizhok."
  items:
    - {file: "r1.md"}
    - {file: "r2.md"}

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

  - id: joiner
    type:join
    from: "fork"
    out: "joined"
    select:
      f: "{{item.file}}"
      a: "{{ctx.approval}}"
      t: "{{ctx.final_branch}}"
    mode: list
    await_nodes: ["finalize"]
    depends: ["finalize"]"""


def _spin_until_inflight(run_id, timeout=5.0):
    start = time.time()
    while time.time() - start < timeout:
        st = load_state(run_id)
        if st and (st.get("inflight") or {}):
            return True
        time.sleep(0.01)
    return False


def test_resume_with_cold_engine_and_complete_human_tasks():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""  # disable external LLMs
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        # 1) Start the run until inflation appears
        eng1 = DAGEngine(load_plan_from_text(PLAN))
        for _ in range(300):
            eng1.tick()
            if _spin_until_inflight(eng1.run_id, timeout=0.0):
                break
            time.sleep(0.005)
        assert (
            load_state(eng1.run_id).get("inflight") or {}
        ), "Inflight for human.reviews did not appear"

        # 2) Simulates a “restart” of the process: creating a cold engine without an initial plan
        st = load_state(eng1.run_id)
        main_nodes = list((st.get("branches", {}).get("main", {}) or {}).get("nodes", {}).keys())
        eng2 = DAGEngine(
            {
                "run_id": eng1.run_id,
                "branch_id": "main",
                "nodes": [{"id": k} for k in main_nodes],
            }
        )

        # 3) We complete all human tasks through on_human_completed() on a cold engine
        inflight_ids = list((st.get("inflight") or {}).keys())
        for tid in inflight_ids:
            assert eng2.on_human_completed(tid, {"result": "OK"}) is True

        # 4) We finish the execution with a cold engine
        run_loop(eng2, poll_interval=0.02)

        st_fin = load_state(eng2.run_id)
        assert st_fin.get("finished") is True
        # Let's check that he has collected the results
        main_ctx = load_context(eng2.run_id, "main")
        joined = main_ctx.get("joined")
        assert isinstance(joined, list) and len(joined) == 2
        for row in joined:
            assert row.get("a") == "OK"
            assert "FINAL" in (row.get("t") or "")
