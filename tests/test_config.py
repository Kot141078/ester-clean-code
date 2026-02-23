# tests/test_config.py
# -*- coding: utf-8 -*-
"""
Testy dlya config.py: proveryaem, chto znacheniya chitayutsya iz ENV i imeyut nuzhnye tipy.
Vazhno: v repozitorii mozhet ne byt zavisimosti python-dotenv — podmenyaem modul 'dotenv'
pered importom config, chtoby izbezhat ImportError.
"""
import importlib
import os
import sys
import types
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _install_fake_dotenv():
    fake = types.ModuleType("dotenv")

    def _noop():
        return None

    fake.load_dotenv = _noop
    sys.modules["dotenv"] = fake


def test_config_env_types_and_defaults(monkeypatch):
    _install_fake_dotenv()

    # Znacheniya cherez ENV
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "5050")
    monkeypatch.setenv("DEBUG", "0")
    monkeypatch.setenv("THREADED", "1")
    monkeypatch.setenv("CORS_ENABLED", "1")
    monkeypatch.setenv("JWT_SECRET", "xjwt")
    monkeypatch.setenv("PERSIST_DIR", "/tmp/ester")
    monkeypatch.setenv("COLLECTION_NAME", "ester_test_mem")
    monkeypatch.setenv("USE_EMBEDDINGS", "1")
    monkeypatch.setenv("EMBEDDINGS_API_BASE", "http://localhost:1234/v1")
    monkeypatch.setenv("EMBEDDINGS_MODEL", "text-embed-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("USE_LOCAL_EMBEDDINGS", "0")
    monkeypatch.setenv("TZ_NAME", "UTC")

    # Nekotorye proekty dobavlyayut esche polya; my ne utverzhdaem, prosto proveryaem bazovye.
    if "config" in sys.modules:
        del sys.modules["config"]
    conf = importlib.import_module("config")

    assert isinstance(conf.HOST, str) and conf.HOST == "127.0.0.1"
    assert isinstance(conf.PORT, int) and conf.PORT == 5050
    assert isinstance(conf.DEBUG, bool) and conf.DEBUG is False
    assert isinstance(conf.THREADED, bool) and conf.THREADED is True
    assert isinstance(conf.CORS_ENABLED, bool) and conf.CORS_ENABLED is True
    assert isinstance(conf.JWT_SECRET, str) and conf.JWT_SECRET == "xjwt"
    assert isinstance(conf.PERSIST_DIR, str) and conf.PERSIST_DIR == "/tmp/ester"
    assert isinstance(conf.COLLECTION_NAME, str) and conf.COLLECTION_NAME == "ester_test_mem"
    assert isinstance(conf.USE_EMBEDDINGS, bool) and conf.USE_EMBEDDINGS is True
    assert isinstance(conf.EMBEDDINGS_API_BASE, str)
    assert isinstance(conf.EMBEDDINGS_MODEL, str)
    # OPENAI_API_KEY mozhet byt pustym — tolko proveryaem tip
    assert isinstance(conf.OPENAI_API_KEY, str)
# assert isinstance(conf.USE_LOCAL_EMBEDDINGS, bool)