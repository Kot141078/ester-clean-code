from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
"""
Shim-modul dlya importa 'yaml' cherez ruamel.yaml, esli PyYAML otsutstvuet.
Ispolzuetsya, naprimer, v routes_root.py dlya /openapi.json.
"""
try:
    import yaml as _pyyaml  # type: ignore

    safe_load = _pyyaml.safe_load  # type: ignore[attr-defined]
except Exception:
    from ruamel.yaml import YAML  # type: ignore

    _yaml = YAML(typ="safe")

    def safe_load(stream):
        if hasattr(stream, "read"):
            return _yaml.load(stream)
        from io import StringIO

        return _yaml.load(StringIO(str(stream)))