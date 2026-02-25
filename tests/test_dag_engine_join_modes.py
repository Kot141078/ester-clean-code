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

PLAN_DICT = """\
run_id: test_run_join_dict_01
branch_id: main
context_init:
  spec: "Sobrat dictionary po klyuchu = file."
  items:
    - {file: "a.md"}
    - {file: "b.md"}
nodes:
  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: []

  - id: analyze
    type: llm.generate
    prompt: "Analiz {{ctx.item.file}}"
    out: "analysis"
    depends: ["fork"]

  - id: finalize
    type: llm.generate
    prompt: "Final po {{ctx.item.file}} iz {{ctx.analysis}}"
    out: "final_branch"
    depends: ["analyze"]

  - id: gather
    type:join
    from: "fork"
    out: "joined_dict"
    select:
      file: "{{item.file}}"
      text: "{{ctx.final_branch}}"
    mode: dict
    key_field: "{{item.file}}"
    await_nodes: ["finalize"]
    depends: ["finalize"]"""

PLAN_TEXT = """\
run_id: test_run_join_text_01
branch_id: main
context_init:
  spec: "Sobrat tekst s razdelitelem."
  items:
    - {file: "x.txt"}
    - {file: "y.txt"}
nodes:
  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: []

  - id: write
    type: script
    update:
      short: "S={{ctx.item.file}}"
    depends: ["fork"]

  - id: joiner
    type: join
    from: "fork"
    out: "joined_text"
    select:
      f: "{{item.file}}"
      s: "{{ctx.short}}"
    mode: text
    separator: "\\n---\\n"
    await_nodes: ["write"]
    depends: ["write"]
"""


def test_join_mode_dict():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        # Disabling external LLMs
        os.environ["LLM_API_BASE"] = ""
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN_DICT))
        run_loop(eng, poll_interval=0.05)

        st = load_state(eng.run_id)
        assert st.get("finished") is True
        ctx = load_context(eng.run_id, "main")
        joined = ctx.get("joined_dict")
        assert isinstance(joined, dict)
        assert "a.md" in joined and "b.md" in joined
        assert joined["a.md"]["file"] == "a.md"
        assert "text" in joined["a.md"]


def test_join_mode_text():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""  # no need for LLM
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        eng = DAGEngine(load_plan_from_text(PLAN_TEXT))
        run_loop(eng, poll_interval=0.05)

        st = load_state(eng.run_id)
        assert st.get("finished") is True
        ctx = load_context(eng.run_id, "main")
        txt = ctx.get("joined_text")
        assert isinstance(txt, str)
        # Both files must meet, as well as the separator
        assert "x.txt" in txt and "y.txt" in txt
        assert "\n---\n" in txt
