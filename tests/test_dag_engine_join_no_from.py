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
run_id: test_run_join_no_from_01
branch_id: main
context_init:
  spec: "Join bez from: sobrat vsekh potomkov tekuschey vetki."
  items:
    - {file: "p1.md"}
    - {file: "p2.md"}
    - {file: "p3.md"}

nodes:
  - id: prepare
    type: script
    update:
      banner: "Obrabotka: {{ctx.spec}}"
    depends: []

  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: ["prepare"]

  - id: analyze
    type: llm.generate
    prompt: "Korotkiy analiz {{ctx.item.file}}. Uchityvay banner={{ctx.banner}}."
    out: "analysis"
    depends: ["fork"]

  - id: finalize
    type: script
    update:
      final_branch: "OK {{ctx.item.file}} :: {{ctx.analysis}}"
    depends: ["analyze"]

  - id: gather_all
    type: join
    out: "joined_all"
    select:
      file: "{{item.file}}"
      final: "{{ctx.final_branch}}"
    mode: list
    await_nodes: ["finalize"]
    depends: ["finalize"]
"""


def test_join_without_from_collects_all_children():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""  # ispolzuem vstroennyy fallback
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN))
        run_loop(eng, poll_interval=0.05)

        st = load_state(eng.run_id)
        assert st.get("finished") is True

        main_ctx = load_context(eng.run_id, "main")
        joined = main_ctx.get("joined_all")
        assert isinstance(joined, list)
        assert len(joined) == 3
        files = sorted([x.get("file") for x in joined])
        assert files == ["p1.md", "p2.md", "p3.md"]
