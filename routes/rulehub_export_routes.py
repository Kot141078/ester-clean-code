# -*- coding: utf-8 -*-
"""routes/rulehub_export_routes.py - Eksport zhurnala RuleHub v NDJSON/CSV.

Endpoint:
  • GET /rulehub/export.ndjson?limit=N&status=ok|err|blocked
  • GET /rulehub/export.csv?limit=N&status=...

Mosty:
- Yavnyy: (Nablyudaemost ↔ Analitika) vygruzka dlya vneshnikh tulov (SIEM/BI).
- Skrytyy #1: (Inzheneriya ↔ Podderzhka) prostoy interfeys, ne zatragivayuschiy yadro RuleHub.
- Skrytyy #2: (Infoteoriya ↔ Diagnostika) filtratsiya po statusu dlya bystrogo triage.

Zemnoy abzats:
This is “lyuk dlya revizorov”: otkryl - vygruzil zhurnal pachkoy, pones v analiz.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, Response, request, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Myagkiy import eksportera
try:
    from modules.thinking.rulehub_export import read_last, to_ndjson, to_csv  # type: ignore
except Exception:  # pragma: no cover
    def read_last(limit: int = 100, status: str | None = None):  # type: ignore
        return []
    def to_ndjson(rows):  # type: ignore
        return ""
    def to_csv(rows):  # type: ignore
        return ""

bp_rulehub_export = Blueprint("rulehub_export", __name__)


def _parse_limit(val: str | None, default: int = 100, lo: int = 1, hi: int = 10000) -> int:
    try:
        n = int(val or default)
        return max(lo, min(n, hi))
    except Exception:
        return default


def _parse_status(val: str | None) -> str | None:
    if not val:
        return None
    v = val.strip().lower()
    return v if v in {"ok", "err", "blocked"} else None


def register(app):  # pragma: no cover
    app.register_blueprint(bp_rulehub_export)


def init_app(app):  # pragma: no cover
    app.register_blueprint(bp_rulehub_export)


@bp_rulehub_export.get("/rulehub/export.ndjson")
def export_ndjson():
    limit = _parse_limit(request.args.get("limit"))
    status = _parse_status(request.args.get("status"))
    rows = read_last(limit=limit, status=status)
    body = to_ndjson(rows)
    return Response(
        body,
        mimetype="application/x-ndjson; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=rulehub.ndjson"},
    )


@bp_rulehub_export.get("/rulehub/export.csv")
def export_csv():
    limit = _parse_limit(request.args.get("limit"))
    status = _parse_status(request.args.get("status"))
    rows = read_last(limit=limit, status=status)
    body = to_csv(rows)
    return Response(
        body,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=rulehub.csv"},
    )


__all__ = ["bp_rulehub_export", "register", "init_app"]
# c=a+b