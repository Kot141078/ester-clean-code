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
run_id: test_run_join_default_select_01
branch_id: main
context_init:
  spec: "Join bez select — dolzhen vernut branch/item/context_keys."
  items:
    - {file: "aa.md"}
    - {file: "bb.md"}

nodes:
  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: []

  - id: annotate
    type: script
    update:
      tag: "TAG={{ctx.item.file}}"
    depends: ["fork"]

  - id: noop_finish
    type: noop
    depends: ["annotate"]

  - id: joiner
    type: join
    from: "fork"
    out: "joined_default"
    mode: list
    await_nodes: ["noop_finish"]
    depends: ["noop_finish"]
"""


def test_join_without_select_produces_default_rows():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""  # isklyuchaem vneshnie vyzovy
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN))
        run_loop(eng, poll_interval=0.05)

        st = load_state(eng.run_id)
        assert st.get("finished") is True

        main_ctx = load_context(eng.run_id, "main")
        rows = main_ctx.get("joined_default")
        assert isinstance(rows, list) and len(rows) == 2
        for row in rows:
            assert isinstance(row, dict)
            # dolzhny prisutstvovat defoltnye polya
            assert "branch" in row
            assert "item" in row
            assert "context_keys" in row and isinstance(row["context_keys"], list)
