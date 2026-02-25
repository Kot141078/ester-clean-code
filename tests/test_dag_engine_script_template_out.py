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
run_id: test_run_script_template_out_01
branch_id: main
context_init:
  spec: "Check script: i update, i template+out odnovremenno."
  items:
    - {file: "t1"}
nodes:
  - id: s1
    type: script
    update:
      a: "A={{ctx.spec}}"
      b: "B={{ctx.spec}}"
    template: "TEMPLATE {{ctx.a}} + {{ctx.b}}"
    out: "tpl"
    depends: []"""


def test_script_updates_and_template_out():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""  # no need for LLM
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN))
        run_loop(eng, poll_interval=0.05)

        st = load_state(eng.run_id)
        assert st.get("finished") is True

        ctx = load_context(eng.run_id, "main")
        assert ctx.get("a", "").startswith("A=")
        assert ctx.get("b", "").startswith("B=")
        assert isinstance(ctx.get("tpl"), str)
        # the template should pick up the new values
        assert "A=" in ctx["tpl"] and "B=" in ctx["tpl"]
