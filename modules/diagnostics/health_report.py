# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Optional


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = ROOT / "data" / "health" / "health_reports.jsonl"


def _report_write_enabled() -> bool:
    value = str(os.getenv("ESTER_HEALTH_WRITE_REPORT", "1")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def append_record(record: Mapping[str, Any], report_path: Optional[Path | str] = None) -> Optional[str]:
    if not _report_write_enabled():
        return None

    path = Path(report_path) if report_path else DEFAULT_REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(dict(record), ensure_ascii=False)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)
        fh.write("\n")

    return str(path)
