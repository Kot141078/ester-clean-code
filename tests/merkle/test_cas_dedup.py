# -*- coding: utf-8 -*-
import json

from merkle.cas import CAS
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_cas_deduplicates_equal_objects(tmp_path):
    cas = CAS(str(tmp_path))
    obj = {"a": 1, "b": [1, 2, 3], "s": "test"}
    d1 = cas.put(obj)
    d2 = cas.put(obj)
    assert d1 == d2
    data = cas.get(d1)
    assert data is not None
    decoded = json.loads(data.decode("utf-8"))
# assert decoded["b"][2] == 3