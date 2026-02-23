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
run_id: test_run_complex_merge_01
branch_id: main
context_init:
  spec: "Sobrat analiz po dvum dokumentam i slit v obschiy otchet."
  items:
    - {file: "a.md"}
    - {file: "b.md"}

nodes:
  - id: outline
    type: llm.generate
    prompt: "Tseli: {{ctx.spec}}"
    out: "outline"
    depends: []

  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: ["outline"]

  - id: analyze
    type: llm.generate
    prompt: "Analiz {{ctx.item.file}} @ {{ctx.outline}}"
    out: "analysis"
    depends: ["fork"]

  - id: finalize
    type: script
    update:
      final_branch: "FINAL {{ctx.item.file}} :: {{ctx.analysis}}"
    depends: ["analyze"]

  - id: gather
    type: join
    from: "fork"
    out: "joined_list"
    select:
      file: "{{item.file}}"
      text: "{{ctx.final_branch}}"
    mode: list
    await_nodes: ["finalize"]
    depends: ["finalize"]

  - id: final_report
    type: llm.generate
    prompt: "Sformiruy obschiy otchet po elementam={{ctx.joined_list}}"
    out: "report"
    depends: ["gather"]
"""


def test_complex_merge_final_report_contains_children_data():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        # ispolzuem evristiku vmesto vneshnego LLM
        os.environ["LLM_API_BASE"] = ""
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN))
        run_loop(eng, poll_interval=0.05)

        st = load_state(eng.run_id)
        assert st.get("finished") is True

        main_ctx = load_context(eng.run_id, "main")
        # proveryaem nalichie join-rezultata i itogovogo otcheta
        assert isinstance(main_ctx.get("joined_list"), list)
        report = main_ctx.get("report")
        assert isinstance(report, str)
        # tak kak llm.generate v fallback vshivaet chast prompta, proverim, chto v tekste est imena faylov
        assert "a.md" in report
        assert "b.md" in report
