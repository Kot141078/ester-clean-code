# -*- coding: utf-8 -*-
import json
import os
import tempfile
import time

from flask import Flask

from modules.graph.dag_engine import load_context, load_state
from routes.graph_routes import bp_graph
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PLAN_HUMAN = """\
run_id: test_run_graph_human_01
branch_id: main
context_init:
  spec: "Minimal plan s human.review."
  items:
    - {file: "one.md"}

nodes:
  - id: fork
    type: fanout
    items: "{{ctx.items}}"
    depends: []

  - id: human_check
    type: human.review
    message: "Check result dlya {{ctx.item.file}}. Answer: OK/popravki."
    out: "approved"
    depends: ["fork"]"""


def _wait_until(cond, timeout=5.0, step=0.05):
    start = time.time()
    while time.time() - start < timeout:
        if cond():
            return True
        time.sleep(step)
    return False


def test_graph_routes_human_flow():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")
        # Create a Flask test application and connect bp_graph
        app = Flask(__name__)
        app.register_blueprint(bp_graph)

        client = app.test_client()

        # Otpravlyaem plan
        resp = client.post("/graph/submit", data=PLAN_HUMAN.encode("utf-8"))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ok") is True
        run_id = data["run_id"]

        # We are waiting for the task to appear on human.review in inflyzhnt
        def has_inflight():
            st = load_state(run_id)
            return bool(st and st.get("inflight"))

        ok = _wait_until(has_inflight, timeout=5.0)
        assert ok, "inflight ne poyavilsya"

        st1 = load_state(run_id)
        inflight = st1.get("inflight") or {}
        assert len(inflight) == 1
        task_id = list(inflight.keys())[0]

        # We answer as a “person”
        resp2 = client.post(
            "/graph/human_complete",
            json={"run_id": run_id, "task_id": task_id, "result": "OK"},
        )
        assert resp2.status_code == 200
        assert resp2.get_json().get("ok") is True

        # We are waiting for the launch to complete
        def finished():
            st = load_state(run_id)
            return bool(st and st.get("finished"))

        assert _wait_until(finished, timeout=5.0)

        # We check that the result is written in the child branch
        child_ctx = load_context(run_id, "main#01")
        assert child_ctx.get("approval") == "OK"
