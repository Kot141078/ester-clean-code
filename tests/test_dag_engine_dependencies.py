# -*- coding: utf-8 -*-
import os
import tempfile

from modules.graph.dag_engine import (
    DAGEngine,
    load_context,
    load_plan_from_text,
    load_state,
    run_loop,
)

PLAN = """\
run_id: test_run_dependencies_01
branch_id: main
context_init:
  spec: "Proverka zavisimostey (depends) i ispolzovaniya znacheniy iz roditelskoy vetki."
  items:
    - {file: "a.txt"}
    - {file: "b.txt"}

nodes:
  - id: outline
    type: llm.generate
    prompt: "Sformiruy plan po TZ: {{ctx.spec}}."
    out: "outline"
    depends: []

  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: ["outline"]

  # On each child branch, check that the value from the network is available
  - id: check_outline
    type: script
    update:
      has_outline: "HAS={{ctx.outline}}"
    depends: ["fork"]

  - id: finalize
    type: noop
    depends: ["check_outline"]

  - id: join
    type:join
    from: "fork"
    out: "joined"
    select:
      file: "{{item.file}}"
      ok: "{{ctx.has_outline}}"
    mode: list
    await_nodes: ["finalize"]
    depends: ["finalize"]"""


def test_dependencies_propagate_parent_context():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""  # disable real requests
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN))
        run_loop(eng, poll_interval=0.05)

        st = load_state(eng.run_id)
        assert st.get("finished") is True

        # We check that in the child branches the variable us_utline is not empty (which means the utline was executed before the fork)
        child1 = load_context(eng.run_id, "main#01")
        child2 = load_context(eng.run_id, "main#02")
        assert child1.get("has_outline", "").startswith("HAS=")
        assert child2.get("has_outline", "").startswith("HAS=")
        assert len(child1.get("has_outline", "")) > 4
        assert len(child2.get("has_outline", "")) > 4

        main_ctx = load_context(eng.run_id, "main")
        joined = main_ctx.get("joined")
        assert isinstance(joined, list) and len(joined) == 2
        for row in joined:
            # ok must start with "US=" and not be empty
            assert (
                isinstance(row.get("ok"), str)
                and row["ok"].startswith("HAS=")
                and len(row["ok"]) > 4
            )
