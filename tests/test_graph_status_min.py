# -*- coding: utf-8 -*-
import os
import tempfile

from flask import Flask

from routes.graph_routes import bp_graph
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PLAN = """\
run_id: test_run_graph_status_min_01
branch_id: main
context_init:
  spec: "Minimalnyy plan dlya proverki /graph/status bez include_ctx."
  items: []
nodes:
  - id: end
    type: noop
    depends: []
"""


def test_graph_status_without_include_ctx():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")

        app = Flask(__name__)
        app.register_blueprint(bp_graph)
        client = app.test_client()

        r = client.post("/graph/submit", data=PLAN.encode("utf-8"))
        assert r.status_code == 200 and r.get_json().get("ok") is True
        run_id = r.get_json()["run_id"]

        r2 = client.get(f"/graph/status/{run_id}")
        assert r2.status_code == 200
        data = r2.get_json()
        assert data.get("ok") is True
        # contexts_index ne dolzhen prisutstvovat po umolchaniyu
        assert "contexts_index" not in data
