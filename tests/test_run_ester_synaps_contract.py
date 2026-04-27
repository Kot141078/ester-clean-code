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


def test_synaps_file_manifest_uses_quarantine_and_skips_background_mirror():
    block = _extract_block(RUN_SOURCE, r"def sister_inbound\(\):", r"return jsonify\(response.body\), response.status_code")
    post_adapter_block = block[block.index("response = _handle_synaps_inbound_payload") :]

    assert "_sister_file_manifest_handler" in block
    assert "_handle_synaps_file_manifest" in block
    assert "_SynapsMessageType.FILE_MANIFEST" in post_adapter_block
    assert post_adapter_block.index("_SynapsMessageType.FILE_MANIFEST") < post_adapter_block.index("_mirror_background_event")
