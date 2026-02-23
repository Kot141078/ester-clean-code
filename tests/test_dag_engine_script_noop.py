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
run_id: test_run_script_noop_01
branch_id: main
context_init:
  spec: "Proverka script i noop."
  items:
    - {file: "m1"}
    - {file: "m2"}

nodes:
  - id: prepare
    type: script
    update:
      banner: "GO {{ctx.spec}}"
    template: "Items={{ctx.items}}"
    out: "hdr"
    depends: []

  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: ["prepare"]

  - id: annotate
    type: script
    update:
      note: "BR={{ctx.item.file}} HDR={{ctx.hdr}} BN={{ctx.banner}}"
    depends: ["fork"]

  - id: noop_finish
    type: noop
    depends: ["annotate"]

  - id: gather
    type: join
    from: "fork"
    out: "joined"
    select:
      f: "{{item.file}}"
      n: "{{ctx.note}}"
    mode: list
    await_nodes: ["noop_finish"]
    depends: ["noop_finish"]
"""


def test_script_and_noop_and_join_list():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""  # isklyuchaem realnye vyzovy
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN))
        run_loop(eng, poll_interval=0.05)

        st = load_state(eng.run_id)
        assert st.get("finished") is True

        # Proverim bazovyy kontekst
        main_ctx = load_context(eng.run_id, "main")
        assert "hdr" in main_ctx and "banner" in main_ctx

        # Proverim dochernie vetki poluchili note
        c1 = load_context(eng.run_id, "main#01")
        c2 = load_context(eng.run_id, "main#02")
        assert "note" in c1 and "note" in c2
        # I chto join sobral spisok
        joined = main_ctx.get("joined")
        assert isinstance(joined, list)
        assert any(row.get("f") == "m1" for row in joined)
        assert any(row.get("f") == "m2" for row in joined)
