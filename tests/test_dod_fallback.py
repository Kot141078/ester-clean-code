# tests/test_dod_fallback.py
# -*- coding: utf-8 -*-
"""Proveryaem fallback-put parse_coverage_xml(), kogda na korne net agregatov
(line-rate/branch-rate/lines-valid/branches-valid = 0 or otsutstvuyut),
i metrics berutsya iz <class line-rate/branch-rate>."""
import importlib
import tempfile
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

check_dod = importlib.import_module("ci.check_dod")

_FALLBACK_XML = """<?xml version="1.0" ?>
<coverage version="7.6.0" timestamp="1726969696">
  <packages>
    <package name="pkg">
      <classes>
        <class name="a" filename="a.py" line-rate="1.0" branch-rate="1.0"></class>
        <class name="b" filename="b.py" line-rate="0.8" branch-rate="0.6"></class>
      </classes>
    </package>
  </packages>
</coverage>
"""


def test_parse_coverage_xml_fallback_from_classes():
    with tempfile.TemporaryDirectory() as td:
        cov = Path(td) / "coverage.xml"
        cov.write_text(_FALLBACK_XML, encoding="utf-8")
        lr, br, lc, lv, bc, bv = check_dod.parse_coverage_xml(str(cov))
        # Fallback-evristika schitaet po klassam:
        # lines_valid = 2 (po odnomu na klass s line-rate)
        # lines_covered: 1 (lr=1.0) + round(0.8)=1  => 2/2 => 1.0
        # branches_valid = 2; branches_covered: 1 + round(0.6)=1 => 2/2 => 1.0
        assert 0.99 <= lr <= 1.0
        assert 0.99 <= br <= 1.0
        assert (lc, lv, bc, bv) == (2, 2, 2, 2)
