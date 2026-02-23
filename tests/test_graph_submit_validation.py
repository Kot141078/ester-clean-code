# -*- coding: utf-8 -*-
import os
import tempfile

from flask import Flask

from routes.graph_routes import bp_graph
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_submit_rejects_empty_body():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DAG_RUN_ROOT"] = os.path.join(tmp, "runs")
        os.environ["DAG_BRANCH_ROOT"] = os.path.join(tmp, "branches")

        app = Flask(__name__)
        app.register_blueprint(bp_graph)
        client = app.test_client()

        r = client.post("/graph/submit", data=b"")
        assert r.status_code == 400
        j = r.get_json()
        assert j.get("ok") is False
        assert j.get("error") == "empty_plan"
