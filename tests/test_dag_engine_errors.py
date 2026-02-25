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

PLAN_UNKNOWN_TYPE = """\
run_id: test_run_unknown_type_01
branch_id: main
context_init:
  spec: "Plan s neizvestnym tipom uzla."
nodes:
  - id: bad
    type: wtf_is_this
    depends: []
"""

PLAN_JOIN_NO_CHILDREN = """\
run_id: test_run_join_no_children_01
branch_id: main
context_init:
  spec: "Fanout generate 0 children; join dolzhen otrabotat korrektno."
  items: []
nodes:
  - id: outline
    type: script
    update:
      note: "ok"
    depends: []

  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: ["outline"]

  - id: join_empty
    type:join
    from: "fork"
    out: "joined"
    mode: list
    await_nodes: []
    depends: ["fork"]"""


def test_unknown_node_type_marks_failed_and_finishes():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""  # isklyuchim internet
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN_UNKNOWN_TYPE))
        run_loop(eng, poll_interval=0.02)

        st = load_state(eng.run_id)
        assert st.get("finished") is True
        nodes = st.get("branches", {}).get("main", {}).get("nodes", {})
        assert nodes.get("bad") == "failed"


def test_join_without_children_is_ok_and_writes_empty_list():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN_JOIN_NO_CHILDREN))
        run_loop(eng, poll_interval=0.02)

        st = load_state(eng.run_id)
        assert st.get("finished") is True
        ctx_main = load_context(eng.run_id, "main")
        assert "joined" in ctx_main
        assert isinstance(ctx_main["joined"], list)
        assert ctx_main["joined"] == []
