from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_reply_contour_memory_probe_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path / "outer"))
    repo_root = Path(__file__).resolve().parents[1]
    probe_state = tmp_path / "probe_state"
    env = dict(os.environ)
    env["ESTER_STATE_DIR"] = str(probe_state)
    cmd = [
        sys.executable,
        str(repo_root / "tools" / "run_reply_contour_memory_probe.py"),
        "--json",
        "--state-dir",
        str(probe_state),
    ]
    proc = subprocess.run(cmd, cwd=str(repo_root), env=env, capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout)

    assert payload["ok"] is True
    assert payload["trace_ready"] is True
    assert payload["memory_self_present"] is True
    assert payload["diagnostics_status"] in {"instrumented", "partial"}
