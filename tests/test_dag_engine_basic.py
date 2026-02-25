# -*- coding: utf-8 -*-
import json
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

PLAN_TEXT = """\
run_id: test_run_dag_basic_01
branch_id: main
context_init:
  spec: "Podgotovit nabroski dlya dvukh elementov i sobrat tekstovyy konsolidirovannyy vyvod."
  items:
    - {file: "doc_1.txt"}
    - {file: "doc_2.txt"}

nodes:
  - id: prepare
    type: script
    update:
      prompt_stub: "Obschiy kontekst: {{ctx.spec}}. Sleduy strukture: vvod, analiz, vyvod."
    template: "Start obrabotki nabora iz {{ctx.items}}"
    out: "header"
    depends: []

  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: ["prepare"]

  - id: analyze
    type: llm.generate
    prompt: "Dlya {{ctx.item.file}}. {{ctx.prompt_stub}} Formuliruy 3–5 predlozheniy."
    out: "analysis"
    depends: ["fork"]

  - id: polish
    type: llm.generate
    prompt: "Otredaktiruy i sozhmi analiz po {{ctx.item.file}}: {{ctx.analysis}}"
    out: "final_branch"
    depends: ["analyze"]

  - id: gather_text
    type:join
    from: "fork"
    out: "consolidated_text"
    select:
      file: "{{item.file}}"
      text: "{{ctx.final_branch}}"
    mode: text
    separator: "\\n---\\n"
    await_nodes: ["polish"]
    depends: ["polish"]"""


def test_dag_engine_fanout_join_text():
    # Izoliruem katalogi vypolneniya
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        # Disable external LLM calls -> use heuristics
        os.environ["LLM_API_BASE"] = ""
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        plan = load_plan_from_text(PLAN_TEXT)
        eng = DAGEngine(plan)
        # Sinkhronnyy progon
        run_loop(eng, poll_interval=0.05)

        # Checking the condition
        st = load_state(eng.run_id)
        assert st.get("finished") is True
        # Itogovyy kontekst osnovnoy vetki
        ctx = load_context(eng.run_id, "main")
        assert "consolidated_text" in ctx
        out = ctx["consolidated_text"]
        assert isinstance(out, str)
        # Both files must be mentioned in the merged text
        assert "doc_1.txt" in out
        assert "doc_2.txt" in out
