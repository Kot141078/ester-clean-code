# -*- coding: utf-8 -*-
import os
import tempfile
import time

from flask import Flask

from modules.graph.dag_engine import load_state
from routes.graph_routes import bp_graph
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PLAN = """\
run_id: test_run_graph_status_ctx_01
branch_id: main
context_init:
  spec: "Plan bez human, chtoby zavershilsya sam."
  items:
    - {file: "n1.md"}
    - {file: "n2.md"}

nodes:
  - id: prepare
    type: script
    update:
      stamp: "ok"
    depends: []

  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: ["prepare"]

  - id: annotate
    type: script
    update:
      tag: "BR={{ctx.item.file}} ST={{ctx.stamp}}"
    depends: ["fork"]

  - id: noop_finish
    type: noop
    depends: ["annotate"]

  - id: gather
    type:join
    from: "fork"
    out: "joined"
    select:
      f: "{{item.file}}"
      t: "{{ctx.tag}}"
    mode: list
    await_nodes: ["noop_finish"]
    depends: ["noop_finish"]"""


def _wait_until(cond, timeout=5.0, step=0.02):
    start = time.time()
    while time.time() - start < timeout:
        if cond():
            return True
        time.sleep(step)
    return False


def test_status_with_context_index():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""  # no need for LLM
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        app = Flask(__name__)
        app.register_blueprint(bp_graph)
        client = app.test_client()

        # submit
        r = client.post("/graph/submit", data=PLAN.encode("utf-8"))
        assert r.status_code == 200 and r.get_json().get("ok") is True
        run_id = r.get_json()["run_id"]

        # wait for completion
        assert _wait_until(lambda: bool(load_state(run_id).get("finished")), timeout=5.0)

        # status request with include_sth=1
        r2 = client.get(f"/graph/status/{run_id}?include_ctx=1")
        assert r2.status_code == 200
        data = r2.get_json()
        assert data.get("ok") is True
        idx = data.get("contexts_index") or {}
        # There must be a main and two child branches
        assert "main" in idx
        # child branches using the main#NN template
        children = [k for k in idx.keys() if k.startswith("main#")]
        assert len(children) == 2
        # the list of context keys must be a list
        assert isinstance(idx["main"], list)
        for ch in children:
            assert isinstance(idx[ch], list)
