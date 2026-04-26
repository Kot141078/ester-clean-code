from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_memory_status_tool_reads_overview(tmp_path, monkeypatch):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))
    repo_root = Path(__file__).resolve().parents[1]

    env = dict(os.environ)
    env["ESTER_STATE_DIR"] = str(tmp_path)
    cmd = [sys.executable, str(repo_root / "tools" / "memory_status.py"), "--json", "--section", "overview"]
    proc = subprocess.run(cmd, cwd=str(repo_root), env=env, capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout)

    assert payload["schema"] == "ester.memory.overview.v1"
    assert payload["storage"]["users_total"] == 0


def test_memory_status_tool_reads_operator(tmp_path, monkeypatch):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))
    repo_root = Path(__file__).resolve().parents[1]

    env = dict(os.environ)
    env["ESTER_STATE_DIR"] = str(tmp_path)
    cmd = [sys.executable, str(repo_root / "tools" / "memory_status.py"), "--json", "--section", "operator"]
    proc = subprocess.run(cmd, cwd=str(repo_root), env=env, capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout)

    assert payload["schema"] == "ester.memory.operator.v1"


def test_memory_status_tool_reads_self_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setenv("ESTER_STATE_DIR", str(tmp_path))
    repo_root = Path(__file__).resolve().parents[1]

    env = dict(os.environ)
    env["ESTER_STATE_DIR"] = str(tmp_path)
    cmd = [sys.executable, str(repo_root / "tools" / "memory_status.py"), "--json", "--section", "self_diagnostics"]
    proc = subprocess.run(cmd, cwd=str(repo_root), env=env, capture_output=True, text=True, check=True)
    payload = json.loads(proc.stdout)

    assert payload.get("state") == "not_materialized" or payload.get("schema") == "ester.memory.self_diagnostics.v1"
