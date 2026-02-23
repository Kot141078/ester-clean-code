# -*- coding: utf-8 -*-
import os
import tempfile
import time

from flask import Flask

from modules.graph.dag_engine import load_state
from routes.graph_routes import bp_graph
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PLAN = """\
run_id: test_run_graph_start_01
branch_id: main
context_init:
  spec: "Plan dlya proverki /graph/start."
  items:
    - {file: "s1.txt"}
    - {file: "s2.txt"}

nodes:
  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: []

  - id: annotate
    type: script
    update:
      note: "BR={{ctx.item.file}}"
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


def _wait_until(cond, timeout=5.0, step=0.02):
    start = time.time()
    while time.time() - start < timeout:
        if cond():
            return True
        time.sleep(step)
    return False


def test_graph_start_endpoint_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        os.environ["LLM_API_BASE"] = ""  # ne nuzhen LLM
        os.environ["LLM_MODEL"] = "gpt-4o-mini"

        app = Flask(__name__)
        app.register_blueprint(bp_graph)
        client = app.test_client()

        # 1) submit srazu startuet vypolnenie
        r = client.post("/graph/submit", data=PLAN.encode("utf-8"))
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True
        run_id = data["run_id"]

        # 2) /graph/start dopuskaetsya vyzyvat povtorno (dolzhno byt OK)
        r2 = client.post("/graph/start", json={"run_id": run_id})
        assert r2.status_code == 200
        assert r2.get_json().get("ok") is True

        # 3) Dozhdatsya zaversheniya
        assert _wait_until(lambda: bool(load_state(run_id).get("finished")), timeout=5.0)
