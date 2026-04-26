from __future__ import annotations

import json

from modules.memory import memory_index
from modules.reports import memory_http


def test_memory_http_materializes_empty_baseline(tmp_path, monkeypatch):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    overview_json = json.loads(memory_http._overview_json())
    health_json = json.loads(memory_http._health_json())
    timeline_json = json.loads(memory_http._timeline_json())
    operator_json = json.loads(memory_http._operator_json())

    assert overview_json["schema"] == "ester.memory.overview.v1"
    assert overview_json["storage"]["users_total"] == 0
    assert health_json["schema"] == "ester.memory.health.v1"
    assert timeline_json["schema"] == "ester.memory.timeline.v1"
    assert operator_json["schema"] == "ester.memory.operator.v1"


def test_memory_http_reads_materialized_memory_index(tmp_path, monkeypatch):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))

    payload = memory_index.ensure_materialized()
    assert payload["ok"] is True

    overview_md = memory_http._overview_md()
    overview_json = json.loads(memory_http._overview_json())
    health_md = memory_http._health_md()
    health_json = json.loads(memory_http._health_json())
    timeline_md = memory_http._timeline_md()
    timeline_json = json.loads(memory_http._timeline_json())
    operator_md = memory_http._operator_md()
    operator_json = json.loads(memory_http._operator_json())
    reply_trace_json = json.loads(memory_http._reply_trace_json())
    self_diagnostics_json = json.loads(memory_http._self_diagnostics_json())

    assert "# memory overview" in overview_md
    assert overview_json["schema"] == "ester.memory.overview.v1"
    assert "# memory health digest" in health_md
    assert health_json["schema"] == "ester.memory.health.v1"
    assert "# memory timeline" in timeline_md
    assert timeline_json["schema"] == "ester.memory.timeline.v1"
    assert "# memory operator" in operator_md
    assert operator_json["schema"] == "ester.memory.operator.v1"
    assert reply_trace_json.get("state") == "not_materialized" or reply_trace_json["schema"] == "ester.reply_trace.v1"
    assert self_diagnostics_json.get("state") == "not_materialized" or self_diagnostics_json["schema"] == "ester.memory.self_diagnostics.v1"


def test_memory_http_registers_fastapi_routes():
    try:
        from fastapi import FastAPI
    except Exception:
        return

    app = FastAPI()
    assert memory_http.register_fastapi(app) is True
    paths = {r.path for r in app.routes}
    assert "/compat/reports/memory/overview.md" in paths
    assert "/compat/reports/memory/overview.json" in paths
    assert "/compat/reports/memory/health.md" in paths
    assert "/compat/reports/memory/health.json" in paths
    assert "/compat/reports/memory/timeline.md" in paths
    assert "/compat/reports/memory/timeline.json" in paths
    assert "/compat/reports/memory/operator.md" in paths
    assert "/compat/reports/memory/operator.json" in paths
    assert "/compat/reports/memory/reply_trace.md" in paths
    assert "/compat/reports/memory/reply_trace.json" in paths
    assert "/compat/reports/memory/self_diagnostics.md" in paths
    assert "/compat/reports/memory/self_diagnostics.json" in paths
