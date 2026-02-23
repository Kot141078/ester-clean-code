# -*- coding: utf-8 -*-
import io
import json

import yaml
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_openapi_yaml_vs_json_subset(client):
    # /openapi.json dolzhen soderzhat kak minimum te zhe puti, chto i openapi.yaml
    r = client.get("/openapi.json")
    assert r.status_code == 200
    j = r.get_json()
    assert isinstance(j, dict)
    json_paths = set((j.get("paths") or {}).keys())

    # chitaem lokalnyy fayl openapi.yaml
    with open("openapi.yaml", "r", encoding="utf-8") as f:
        y = yaml.safe_load(f)
    yaml_paths = set((y.get("paths") or {}).keys())

    # peresechenie dolzhno byt suschestvennym: minimum 70% putey iz yaml
    common = yaml_paths & json_paths
    assert yaml_paths, "openapi.yaml bez paths"
    ratio = len(common) / max(1, len(yaml_paths))
    assert (
        ratio >= 0.7
), f"slishkom malo obschikh putey ({len(common)}/{len(yaml_paths)})"