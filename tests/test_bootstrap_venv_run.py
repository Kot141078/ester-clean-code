from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_BOOTSTRAP_PATH = Path(__file__).resolve().parents[1] / "tools" / "bootstrap_venv_run.py"
_SPEC = importlib.util.spec_from_file_location("bootstrap_venv_run_test", _BOOTSTRAP_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def test_bootstrap_resolve_entry_from_root() -> None:
    root = Path(r"C:\Projects\ester")
    entry = _MOD._resolve_entry(root, "run_ester_fixed.py")
    assert entry == root / "run_ester_fixed.py"


def test_bootstrap_removes_foreign_site_packages(monkeypatch) -> None:
    original = list(sys.path)
    project_root = r"C:\Projects\ester"
    venv_site = project_root + r"\.venv\Lib\site-packages"
    user_site = r"C:\Users\example\AppData\Roaming\Python\Python310\site-packages"
    sys.path[:] = [
        project_root,
        r"C:\Python310\lib\site-packages",
        venv_site,
        user_site,
    ]
    try:
        _MOD._remove_foreign_site_packages(Path(venv_site))
        assert r"C:\Python310\lib\site-packages" not in sys.path
        assert user_site not in sys.path
        assert venv_site in sys.path
    finally:
        sys.path[:] = original


def test_bootstrap_normalizes_hf_cache_env() -> None:
    env = {
        "TRANSFORMERS_CACHE": r"D:\old\tf",
        "PYTORCH_TRANSFORMERS_CACHE": r"D:\old\pt_tf",
        "PYTORCH_PRETRAINED_BERT_CACHE": r"D:\old\bert",
    }

    project_root = Path(r"C:\Projects\ester")
    _MOD._normalize_hf_cache_env(project_root, env)

    assert env["HF_HOME"] == str((project_root / "data" / "cache" / "huggingface").resolve())
    assert env["HUGGINGFACE_HUB_CACHE"] == str((Path(env["HF_HOME"]) / "hub").resolve())
    assert "TRANSFORMERS_CACHE" not in env
    assert "PYTORCH_TRANSFORMERS_CACHE" not in env
    assert "PYTORCH_PRETRAINED_BERT_CACHE" not in env


def test_bootstrap_detects_module_invocation() -> None:
    assert _MOD._is_module_invocation(["-m", "listeners.telegram_bot"]) is True
    assert _MOD._is_module_invocation(["run_ester_fixed.py"]) is False
