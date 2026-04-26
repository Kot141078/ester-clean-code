from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_SOURCE = (ROOT / "run_ester_fixed.py").read_text(encoding="utf-8")


def _extract_block(source: str, start_pat: str, end_pat: str) -> str:
    match = re.search(start_pat + r".*?" + end_pat, source, re.S)
    assert match, f"block not found: {start_pat} -> {end_pat}"
    return match.group(0)


def test_synaps_thought_probe_does_not_write_background_mirror():
    block = _extract_block(RUN_SOURCE, r"def _sister_thought_handler\(envelope\):", r"return thought")

    assert 'envelope.metadata.get("probe") != "synaps_probe"' in block
    assert 'envelope.metadata.get("memory") != "off"' in block
    assert 'envelope.metadata.get("autochat_window") != "oneshot"' in block
    guard_pos = block.index('envelope.metadata.get("probe") != "synaps_probe"')
    mirror_pos = block.index("_mirror_background_event")

    assert guard_pos < mirror_pos
    assert "[SISTER_THOUGHT_REQUEST]" in block
