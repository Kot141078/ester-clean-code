# tests/test_dod.py
# -*- coding: utf-8 -*-
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Importiruem tselevoy modul odin raz (pod svoim putem)
check_dod = importlib.import_module("ci.check_dod")

_COV_OK_XML = """<?xml version="1.0" ?>
<coverage branch-rate="0.90" branches-covered="90" branches-valid="100"
          line-rate="0.92" lines-covered="92" lines-valid="100"
          version="7.6.0" timestamp="1726969696">
  <packages></packages>
</coverage>
"""

_COV_BAD_XML = """<?xml version="1.0" ?>
<coverage branch-rate="0.80" branches-covered="80" branches-valid="100"
          line-rate="0.81" lines-covered="81" lines-valid="100"
          version="7.6.0" timestamp="1726969696">
  <packages></packages>
</coverage>
"""


def _run_main_with(tmpdir: Path, xml_text: str, thr_lines="0.85", thr_br="0.85"):
    cov = tmpdir / "coverage.xml"
    out = tmpdir / "dod_status.json"
    cov.write_text(xml_text, encoding="utf-8")
    # Porogovye znacheniya cherez ENV
    os.environ["DOD_LINES_MIN"] = thr_lines
    os.environ["DOD_BRANCH_MIN"] = thr_br

    # Podmenyaem argv dlya main()
    argv_backup = sys.argv[:]
    try:
        sys.argv = [
            "check_dod.py",
            "--coverage-xml",
            str(cov),
            "--output-json",
            str(out),
        ]
        rc = check_dod.main()
    finally:
        sys.argv = argv_backup
    assert out.exists(), "Ozhidalsya dod_status.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    return rc, payload


def test_parse_coverage_xml_ok():
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        cov = tmpdir / "coverage.xml"
        cov.write_text(_COV_OK_XML, encoding="utf-8")
        lr, br, lc, lv, bc, bv = check_dod.parse_coverage_xml(str(cov))
        assert 0.91 <= lr <= 0.93
        assert 0.89 <= br <= 0.91
        assert (lc, lv, bc, bv) == (92, 100, 90, 100)


def test_main_pass_ok_thresholds():
    with tempfile.TemporaryDirectory() as td:
        rc, payload = _run_main_with(Path(td), _COV_OK_XML, "0.85", "0.85")
        assert rc == 0
        assert payload["ok"] is True
        assert payload["checks"]["lines_ok"] is True
        assert payload["checks"]["branches_ok"] is True
        assert 0.91 <= payload["coverage"]["lines"]["rate"] <= 0.93


def test_main_fail_low_coverage():
    with tempfile.TemporaryDirectory() as td:
        rc, payload = _run_main_with(Path(td), _COV_BAD_XML, "0.85", "0.85")
        assert rc == 1
        assert payload["ok"] is False
        assert payload["checks"]["lines_ok"] is False
        assert payload["checks"]["branches_ok"] is False


def test_main_missing_file_returns_rc2():
    with tempfile.TemporaryDirectory() as td:
        # Ne sozdaem coverage.xml — proverim obrabotku oshibki
        out = Path(td) / "dod_status.json"
        # Porogovye po umolchaniyu
        os.environ.pop("DOD_LINES_MIN", None)
        os.environ.pop("DOD_BRANCH_MIN", None)

        argv_backup = sys.argv[:]
        try:
            sys.argv = [
                "check_dod.py",
                "--coverage-xml",
                str(Path(td) / "coverage.xml"),
                "--output-json",
                str(out),
            ]
            rc = check_dod.main()
        finally:
            sys.argv = argv_backup

        assert rc == 2
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["ok"] is False
        assert data["error"] in {"coverage_xml_not_found", "coverage_xml_parse_error"}
