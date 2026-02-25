# ci/check_dod.py
# -*- coding: utf-8 -*-
"""Check Definition of Done po pokrytiyu testami.
Sovmestimo s coverage.py XML (format Cobertura ot pytest-cov).

- Read coverage.xml.
- Izvlekaet metrics: lines-covered/valid, branches-covered/valid i sootvetstvuyuschie rates.
- Sravnivaet s porogami iz ENV:
    DOD_LINES_MIN (by default 0.85)
    DOD_BRANCH_MIN (by default 0.85)
- Pishet dod_status.json s detailnoy svodkoy.
- Code vykhoda:
    0 — porogi soblyudeny
    1 - porogi NE soblyudeny
    2 - oshibka (for example, ne nayden fayl, parsing i t.p.)

Signatury/puti: drop-in dlya dampa (vyzyvaetsya iz ci/check_dod.sh)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from typing import Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _to_float(val: str | None, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except Exception:
        return default


def _safe_div(n: float, d: float) -> float:
    return (n / d) if d else 0.0


def parse_coverage_xml(path: str) -> Tuple[float, float, int, int, int, int]:
    """
    Vozvraschaet:
      (line_rate, branch_rate, lines_covered, lines_valid, branches_covered, branches_valid)
    """
    tree = ET.parse(path)
    root = tree.getroot()

    # coverage.py xml (cobertura-like) khranit summarnye atributy na kornevom elemente:
    #   line-rate, lines-covered, lines-valid, branch-rate, branches-covered, branches-valid
    line_rate = _to_float(root.attrib.get("line-rate"))
    branch_rate = _to_float(root.attrib.get("branch-rate"))

    lines_covered = int(root.attrib.get("lines-covered", "0"))
    lines_valid = int(root.attrib.get("lines-valid", "0"))

    branches_covered = int(root.attrib.get("branches-covered", "0"))
    branches_valid = int(root.attrib.get("branches-valid", "0"))

    # In case some attributes are missing, we aggregate manually
    # from <packages>/<classes>/<lines>/<line> or <class> matrix, but this is rarely needed.
    # We cover false information only if rate == 0 and valid == 0.
    if (line_rate == 0.0 and lines_valid == 0) or (branch_rate == 0.0 and branches_valid == 0):
        # Let's try to summarize by class (this happens in the Sobertour format)
        total_lines_valid = 0
        total_lines_covered = 0
        total_branches_valid = 0
        total_branches_covered = 0

        for cls in root.findall(".//class"):
            # Po spetsifikatsii cobertura u class est attributes:
            #   line-rate, branch-rate, complexity, filename, name
            lr = _to_float(cls.attrib.get("line-rate"), None)
            br = _to_float(cls.attrib.get("branch-rate"), None)

            # If line details are available:
            # Let's walk along the <lines>/<line pros="" brunch="" condition-soverage="">
            # But it’s not easy to summarize accurately—we use rate heuristics if the validity is unknown.
            # In order not to complicate things, if the valid is not a tribute, we skip it - in practice, there are always root attributes.
            if lr is not None:
                # let's say 1 class = 1 weight unit; this is just a backup mode
                total_lines_valid += 1
                total_lines_covered += 1 if lr >= 1.0 else int(round(lr))

            if br is not None:
                total_branches_valid += 1
                total_branches_covered += 1 if br >= 1.0 else int(round(br))

        if lines_valid == 0 and total_lines_valid > 0:
            lines_valid = total_lines_valid
            lines_covered = total_lines_covered
            line_rate = _safe_div(lines_covered, lines_valid)

        if branches_valid == 0 and total_branches_valid > 0:
            branches_valid = total_branches_valid
            branches_covered = total_branches_covered
            branch_rate = _safe_div(branches_covered, branches_valid)

    return (
        line_rate,
        branch_rate,
        lines_covered,
        lines_valid,
        branches_covered,
        branches_valid,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coverage-xml", default="coverage.xml")
    ap.add_argument("--output-json", default="dod_status.json")
    args = ap.parse_args()

    cov_path = args.coverage_xml
    out_path = args.output_json

    if not os.path.isfile(cov_path):
        payload = {
            "ok": False,
            "error": "coverage_xml_not_found",
            "file": cov_path,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return 2

    try:
        line_rate, branch_rate, lines_cov, lines_total, br_cov, br_total = parse_coverage_xml(
            cov_path
        )
    except Exception as e:
        payload = {
            "ok": False,
            "error": "coverage_xml_parse_error",
            "file": cov_path,
            "details": f"{type(e).__name__}: {e}",
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return 2

    # Porogovye znacheniya
    thr_lines = float(os.getenv("DOD_LINES_MIN", "0.85"))
    thr_branch = float(os.getenv("DOD_BRANCH_MIN", "0.85"))

    ok_lines = line_rate >= thr_lines
    ok_branch = branch_rate >= thr_branch
    ok = bool(ok_lines and ok_branch)

    payload = {
        "ok": ok,
        "thresholds": {
            "lines": thr_lines,
            "branches": thr_branch,
        },
        "coverage": {
            "lines": {
                "covered": lines_cov,
                "total": lines_total,
                "rate": round(line_rate, 6),
            },
            "branches": {
                "covered": br_cov,
                "total": br_total,
                "rate": round(branch_rate, 6),
            },
        },
        "checks": {"lines_ok": ok_lines, "branches_ok": ok_branch},
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 0 — proydeno, 1 — ne proydeno
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
