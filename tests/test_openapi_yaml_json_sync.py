# -*- coding: utf-8 -*-
import io
import json

import yaml
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_openapi_yaml_vs_json_subset(client):
    # /openapi.jsion must contain at least the same paths as openapi.yml
    r = client.get("/openapi.json")
    assert r.status_code == 200
    j = r.get_json()
    assert isinstance(j, dict)
    json_paths = set((j.get("paths") or {}).keys())

    # read the local file openapi.yaml
    with open("openapi.yaml", "r", encoding="utf-8") as f:
        y = yaml.safe_load(f)
    yaml_paths = set((y.get("paths") or {}).keys())

    # the intersection must be significant: at least 70% of the paths are from Yaml
    common = yaml_paths & json_paths
    assert yaml_paths, "openapi.yaml bez paths"
    ratio = len(common) / max(1, len(yaml_paths))
    assert (
        ratio >= 0.7
), f"too few common paths (ЗЗФ0З/ЗЗФ1ЗЗ)"