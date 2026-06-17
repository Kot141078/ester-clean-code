# -*- coding: utf-8 -*-
from __future__ import annotations

import builtins
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_chat_route_import_does_not_require_openai_or_network():
    script = r"""
import builtins
import urllib.request

orig_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "openai" or name.startswith("openai."):
        raise ModuleNotFoundError("No module named 'openai'")
    return orig_import(name, globals, locals, fromlist, level)

def blocked_urlopen(*args, **kwargs):
    raise AssertionError("network discovery during import")

builtins.__import__ = guarded_import
urllib.request.urlopen = blocked_urlopen

import providers.pool as pool
assert pool.PROVIDERS._loaded is False
assert pool.PROVIDERS._cfg == {}

import routes.chat_routes  # noqa: F401

assert pool.PROVIDERS._loaded is False
assert pool.PROVIDERS._cfg == {}
print("import-safe")
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "import-safe" in proc.stdout


def test_client_path_reports_missing_openai_sdk(monkeypatch):
    import providers.pool as pool

    monkeypatch.setenv("LMSTUDIO_AUTO_MODEL", "0")
    monkeypatch.setattr(
        pool,
        "_fetch_openai_models",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected discovery")),
    )

    orig_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "openai" or name.startswith("openai."):
            raise ImportError("blocked openai import for test")
        return orig_import(name, globals, locals, fromlist, level)

    provider_pool = pool.ProviderPool(autoload=False)
    provider_pool.reload(discover_models=False)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(pool.ProviderUnavailable, match="openai SDK is not installed"):
        provider_pool.client("local")
