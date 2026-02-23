# -*- coding: utf-8 -*-
import asyncio

from proactive_pipeline import run_proactive_thoughts


def test_run_proactive_thoughts():
    result = asyncio.run(
        run_proactive_thoughts("test query", "Owner", "podruga", "proactive_rules.yml")
    )
    assert "agenda" in result
    assert "generated_response" in result
