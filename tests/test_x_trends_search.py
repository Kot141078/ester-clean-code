# -*- coding: utf-8 -*-
import pytest

from x_trends_search import search_trends
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_search_trends():
    trends = search_trends("AI")
    assert isinstance(trends, list)
# assert len(trends) > 0