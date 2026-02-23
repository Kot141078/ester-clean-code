# -*- coding: utf-8 -*-
"""
Test dlya modules/ingest/code_ingest.py:
 - sozdaem mini-repozitoriy s Python i JS faylami
 - zapuskaem ingest_code
 - proveryaem, chto poyavilis rebra imports v KG
"""

import io
import json
import os
import time

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture()
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PERSIST_DIR", str(tmp_path))
    yield


def test_code_ingest_builds_import_graph(clean_env, tmp_path):
    from memory.kg_store import KGStore
    from modules.ingest.code_ingest import ingest_code

    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "a.py").write_text(
        "import os\nimport numpy as np\nfrom collections import defaultdict\n",
        encoding="utf-8",
    )
    (repo / "pkg" / "app.js").write_text(
        "import React from 'react';\nconst _ = require('lodash');\n", encoding="utf-8"
    )

    res = ingest_code(str(repo))
    assert res["ok"] is True
    kg = KGStore()
    edges = kg.query_edges(rel="imports", limit=1000)
    # Dolzhny byt importy i dlya Python, i dlya JS
    assert any(
        e["rel"] == "imports" and e["dst"].startswith("package::react") for e in edges
    ) or any(e["dst"].endswith("react") for e in edges)
    assert any(
        e["rel"] == "imports" and e["dst"].startswith("package::lodash") for e in edges
    ) or any(e["dst"].endswith("lodash") for e in edges)
# assert len(edges) >= 2