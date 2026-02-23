# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler

try:
    from tools.diag_templates_routes import render_markdown
except Exception:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from tools.diag_templates_routes import render_markdown


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dedupe_keep_order(items: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _http_get(url: str, timeout: float) -> Dict[str, Any]:
    opener = build_opener(HTTPRedirectHandler())
    req = Request(url=url, method="GET")
    try:
        with opener.open(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 0) or resp.getcode() or 0)
            final_url = str(resp.geturl() or url)
            return {"status": status, "final_url": final_url, "error": None}
    except HTTPError as exc:
        status = int(getattr(exc, "code", 0) or 0)
        final_url = str(exc.geturl() or url)
        return {"status": status, "final_url": final_url, "error": None}
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.timeout):
            err = "timeout"
        else:
            err = str(reason)
        return {"status": "ERR", "final_url": url, "error": err}
    except Exception as exc:
        return {"status": "ERR", "final_url": url, "error": str(exc)}


def _server_reachable(base: str, timeout: float) -> bool:
    probe_url = urljoin(base.rstrip("/") + "/", "admin")
    data = _http_get(probe_url, timeout=max(0.1, timeout))
    return str(data.get("status")) != "ERR"


def _candidate_paths(report: Dict[str, Any]) -> List[str]:
    candidates = ["/admin", "/admin/portal", "/portal", "/"]
    for item in report.get("flask_render_routes", []):
        rule = str(item.get("rule", "")).strip()
        if not rule or "<" in rule:
            continue
        if not rule.startswith("/"):
            continue
        candidates.append(rule)
    return _dedupe_keep_order(candidates)


def _update_reports(
    *,
    report: Dict[str, Any],
    smoke_rows: List[Dict[str, Any]],
    report_json_path: Path,
    report_md_path: Path,
) -> None:
    report["ui_http_smoke_generated_at"] = _iso_now()
    report["ui_http_smoke"] = smoke_rows
    report_json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_md_path.write_text(render_markdown(report), encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="HTTP smoke for portal/admin UI routes.")
    parser.add_argument("--base", default="http://127.0.0.1:8090", help="Base URL for local Ester instance.")
    parser.add_argument("--project", default=".", help="Project root path.")
    parser.add_argument("--timeout", type=float, default=2.0, help="Request timeout in seconds.")
    parser.add_argument("--json-out", default="ui_http_smoke.json", help="Output smoke JSON path.")
    parser.add_argument("--report-json", default="ui_report.json", help="UI report JSON path.")
    parser.add_argument("--report-md", default="UI_REPORT.md", help="UI report markdown path.")
    args = parser.parse_args(argv)

    root = Path(args.project).resolve()
    base = args.base.strip().rstrip("/")
    json_out_path = (root / args.json_out).resolve()
    report_json_path = (root / args.report_json).resolve()
    report_md_path = (root / args.report_md).resolve()

    report = _load_json(report_json_path)
    if not _server_reachable(base, timeout=float(args.timeout)):
        smoke_payload = {
            "generated_at": _iso_now(),
            "base": base,
            "rows": [],
            "error": "server_unreachable",
        }
        json_out_path.write_text(
            json.dumps(smoke_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report["ui_http_smoke_generated_at"] = _iso_now()
        report["ui_http_smoke"] = []
        report["ui_http_smoke_error"] = "server_unreachable"
        report_json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report_md_path.write_text(render_markdown(report), encoding="utf-8")
        print("UI_HTTP_SMOKE_DONE")
        print(f"base={base}")
        print("rows=0")
        print("reachable=0")
        print(f"json={json_out_path}")
        print("server_unreachable")
        return 2

    paths = _candidate_paths(report)

    rows: List[Dict[str, Any]] = []
    for path in paths:
        full_url = urljoin(base + "/", path.lstrip("/"))
        resp = _http_get(full_url, timeout=max(0.1, float(args.timeout)))
        status = resp["status"]
        final_url = str(resp.get("final_url") or full_url)
        rows.append(
            {
                "path": path,
                "url": full_url,
                "status": status,
                "final_url": final_url,
                "redirected": final_url != full_url,
                "error": resp.get("error"),
            }
        )

    smoke_payload = {
        "generated_at": _iso_now(),
        "base": base,
        "rows": rows,
    }
    json_out_path.write_text(
        json.dumps(smoke_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _update_reports(
        report=report,
        smoke_rows=rows,
        report_json_path=report_json_path,
        report_md_path=report_md_path,
    )

    reachable = any(str(row.get("status")) != "ERR" for row in rows)
    print("UI_HTTP_SMOKE_DONE")
    print(f"base={base}")
    print(f"rows={len(rows)}")
    print(f"reachable={int(reachable)}")
    print(f"json={json_out_path}")
    if not reachable:
        print("server_unreachable")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
