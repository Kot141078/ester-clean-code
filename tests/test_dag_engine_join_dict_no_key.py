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
run_id: test_run_join_dict_no_key_01
branch_id: main
context_init:
  spec: "DICT join bez key_field - klyuchi dolzhny byt imenami vetok (main#NN)."
  items:
    - {file: "f1.md"}
    - {file: "f2.md"}
nodes:
  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: []

  - id: write
    type: script
    update:
      val: "VAL={{ctx.item.file}}"
    depends: ["fork"]

  - id: joiner
    type:join
    from: "fork"
    out: "joined_dict"
    select:
      file: "{{item.file}}"
      v: "{{ctx.val}}"
    mode: dict
    # key_field ne zadan
    await_nodes: ["write"]
    depends: ["write"]"""


def test_join_dict_without_key_field_uses_branch_names():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""  # exclude external calls
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN))
        run_loop(eng, poll_interval=0.05)

        st = load_state(eng.run_id)
        assert st.get("finished") is True

        main_ctx = load_context(eng.run_id, "main")
        d = main_ctx.get("joined_dict")
        assert isinstance(d, dict)
        # the keys must match the names of the child branches
        assert set(d.keys()) == {"main#01", "main#02"}
        for k, row in d.items():
            assert isinstance(row, dict)
            assert "file" in row and "v" in row
            assert row["v"].startswith("VAL=")
