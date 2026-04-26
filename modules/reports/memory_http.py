# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


_PREFIX = os.getenv("ESTER_REPORTS_PREFIX", "/compat/reports")


def _not_materialized_md(title: str, path: Path) -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            "- state: not_materialized",
            f"- path: `{path}`",
            "",
            "_c=a+b_",
        ]
    )


def _read_text(path: Path, *, fallback_title: str) -> str:
    try:
        from modules.memory import memory_index

        memory_index.ensure_materialized()
    except Exception:
        pass
    try:
        text = path.read_text(encoding="utf-8")
        if str(text or "").strip():
            return text
    except Exception:
        pass
    return _not_materialized_md(fallback_title, path)


def _read_json_text(path: Path) -> str:
    try:
        from modules.memory import memory_index

        memory_index.ensure_materialized()
    except Exception:
        pass
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except Exception:
        return json.dumps({"ok": True, "state": "not_materialized", "path": str(path)}, ensure_ascii=False, indent=2)


def _overview_md() -> str:
    from modules.memory import memory_index

    return _read_text(memory_index.overview_digest_path(), fallback_title="Ester — Memory Overview")


def _overview_json() -> str:
    from modules.memory import memory_index

    return _read_json_text(memory_index.overview_path())


def _health_md() -> str:
    from modules.memory import memory_index

    return _read_text(memory_index.health_digest_path(), fallback_title="Ester — Memory Health")


def _health_json() -> str:
    from modules.memory import memory_index

    return _read_json_text(memory_index.health_path())


def _timeline_md() -> str:
    from modules.memory import memory_index

    return _read_text(memory_index.timeline_digest_path(), fallback_title="Ester — Memory Timeline")


def _timeline_json() -> str:
    from modules.memory import memory_index

    return _read_json_text(memory_index.timeline_path())


def _operator_md() -> str:
    from modules.memory import memory_index

    return _read_text(memory_index.operator_digest_path(), fallback_title="Ester — Memory Operator")


def _operator_json() -> str:
    from modules.memory import memory_index

    return _read_json_text(memory_index.operator_path())


def _reply_trace_md() -> str:
    from modules.memory import reply_trace

    return _read_text(Path(reply_trace.latest_digest_path()), fallback_title="Ester — Memory Reply Trace")


def _reply_trace_json() -> str:
    from modules.memory import reply_trace

    return _read_json_text(Path(reply_trace.latest_path()))


def _self_diagnostics_md() -> str:
    from modules.memory import self_diagnostics

    try:
        self_diagnostics.ensure_materialized()
    except Exception:
        pass
    return _read_text(Path(self_diagnostics.latest_digest_path()), fallback_title="Ester — Memory Self Diagnostics")


def _self_diagnostics_json() -> str:
    from modules.memory import self_diagnostics

    try:
        self_diagnostics.ensure_materialized()
    except Exception:
        pass
    return _read_json_text(Path(self_diagnostics.latest_path()))


def register_fastapi(app, prefix: Optional[str] = None) -> bool:
    try:
        from fastapi import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX

    @app.get(prefix + "/memory/overview.md", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_overview_md():
        return Response(content=_overview_md(), media_type="text/markdown")

    @app.get(prefix + "/memory/overview.json", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_overview_json():
        return Response(content=_overview_json(), media_type="application/json")

    @app.get(prefix + "/memory/health.md", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_health_md():
        return Response(content=_health_md(), media_type="text/markdown")

    @app.get(prefix + "/memory/health.json", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_health_json():
        return Response(content=_health_json(), media_type="application/json")

    @app.get(prefix + "/memory/timeline.md", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_timeline_md():
        return Response(content=_timeline_md(), media_type="text/markdown")

    @app.get(prefix + "/memory/timeline.json", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_timeline_json():
        return Response(content=_timeline_json(), media_type="application/json")

    @app.get(prefix + "/memory/operator.md", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_operator_md():
        return Response(content=_operator_md(), media_type="text/markdown")

    @app.get(prefix + "/memory/operator.json", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_operator_json():
        return Response(content=_operator_json(), media_type="application/json")

    @app.get(prefix + "/memory/reply_trace.md", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_reply_trace_md():
        return Response(content=_reply_trace_md(), media_type="text/markdown")

    @app.get(prefix + "/memory/reply_trace.json", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_reply_trace_json():
        return Response(content=_reply_trace_json(), media_type="application/json")

    @app.get(prefix + "/memory/self_diagnostics.md", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_self_diagnostics_md():
        return Response(content=_self_diagnostics_md(), media_type="text/markdown")

    @app.get(prefix + "/memory/self_diagnostics.json", response_class=__import__("fastapi").Response)  # type: ignore
    def _memory_route_self_diagnostics_json():
        return Response(content=_self_diagnostics_json(), media_type="application/json")

    return True


def register_flask(app, prefix: Optional[str] = None) -> bool:
    try:
        from flask import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX

    @app.get(prefix + "/memory/overview.md", endpoint="memory_overview_md")
    def _memory_route_overview_md():
        return Response(_overview_md(), mimetype="text/markdown")

    @app.get(prefix + "/memory/overview.json", endpoint="memory_overview_json")
    def _memory_route_overview_json():
        return Response(_overview_json(), mimetype="application/json")

    @app.get(prefix + "/memory/health.md", endpoint="memory_health_md")
    def _memory_route_health_md():
        return Response(_health_md(), mimetype="text/markdown")

    @app.get(prefix + "/memory/health.json", endpoint="memory_health_json")
    def _memory_route_health_json():
        return Response(_health_json(), mimetype="application/json")

    @app.get(prefix + "/memory/timeline.md", endpoint="memory_timeline_md")
    def _memory_route_timeline_md():
        return Response(_timeline_md(), mimetype="text/markdown")

    @app.get(prefix + "/memory/timeline.json", endpoint="memory_timeline_json")
    def _memory_route_timeline_json():
        return Response(_timeline_json(), mimetype="application/json")

    @app.get(prefix + "/memory/operator.md", endpoint="memory_operator_md")
    def _memory_route_operator_md():
        return Response(_operator_md(), mimetype="text/markdown")

    @app.get(prefix + "/memory/operator.json", endpoint="memory_operator_json")
    def _memory_route_operator_json():
        return Response(_operator_json(), mimetype="application/json")

    @app.get(prefix + "/memory/reply_trace.md", endpoint="memory_reply_trace_md")
    def _memory_route_reply_trace_md():
        return Response(_reply_trace_md(), mimetype="text/markdown")

    @app.get(prefix + "/memory/reply_trace.json", endpoint="memory_reply_trace_json")
    def _memory_route_reply_trace_json():
        return Response(_reply_trace_json(), mimetype="application/json")

    @app.get(prefix + "/memory/self_diagnostics.md", endpoint="memory_self_diagnostics_md")
    def _memory_route_self_diagnostics_md():
        return Response(_self_diagnostics_md(), mimetype="text/markdown")

    @app.get(prefix + "/memory/self_diagnostics.json", endpoint="memory_self_diagnostics_json")
    def _memory_route_self_diagnostics_json():
        return Response(_self_diagnostics_json(), mimetype="application/json")

    return True
