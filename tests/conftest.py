# tests/conftest.py
# -*- coding: utf-8 -*-
"""
Globalnye nastroyki pytest dlya stabilnosti CI:
— Fiksiruem TZ, chtoby testy, zavisyaschie ot vremeni/logov, ne plavali.
— Otklyuchaem setevye pobochki po umolchaniyu.
— Chistim klyuchevye ENV, chtoby import app.py ne padal ot otsutstvuyuschikh integratsiy.
"""
import os
import io

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.fixture(autouse=True, scope="session")
def _ci_env_guard():
    os.environ.setdefault("TZ_NAME", "UTC")
    os.environ.setdefault("ALLOW_NET", "0")
    # Bazovye znacheniya, chtoby importy moduley, ozhidayuschikh konfig, ne padali
    os.environ.setdefault("PRIMARY_PROVIDER", "local")
    os.environ.setdefault("K_RETRIEVAL", "8")
    os.environ.setdefault("MIN_MEAN_SCORE", "0.0")
    os.environ.setdefault("MIN_TOP_SCORE", "0.0")
    os.environ.setdefault("PROACTIVE_RULES_PATH", "config/proactive_rules.yaml")
    os.environ.setdefault("DREAMS_RULES_PATH", "config/dreams_rules.yaml")
    # Telegram & gruppovoy rezhim
    os.environ.setdefault("ESTER_DEFAULT_USER", "default")
    os.environ.setdefault("ESTER_GROUP_MODE", "0")
    os.environ.setdefault("ESTER_GROUP_WHITELIST", "")
    os.environ.setdefault("TELEGRAM_CHAT_ID", "")
    os.environ.setdefault("TELEGRAM_TOKEN", "")
# yield


@pytest.fixture(autouse=True, scope="session")
def _multipart_compat_legacy_tuple():
    """
    Compatibility shim for legacy test payloads:
      {"file": ("name.ext", b"...", "mime/type")}
    Werkzeug expects (fileobj, filename, content_type), so without this shim it
    tries to open "name.ext" from disk and fails with FileNotFoundError.
    """
    try:
        from werkzeug.datastructures import FileMultiDict
    except Exception:
        yield
        return

    orig_add_file = FileMultiDict.add_file

    def _patched_add_file(self, name, file, filename=None, content_type=None):
        if isinstance(file, str) and isinstance(filename, (bytes, bytearray)):
            stream = io.BytesIO(bytes(filename))
            return orig_add_file(self, name, stream, file, content_type)
        return orig_add_file(self, name, file, filename, content_type)

    FileMultiDict.add_file = _patched_add_file
    try:
        yield
    finally:
        FileMultiDict.add_file = orig_add_file


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def app():
    from app import app as flask_app

    # Determiniruem nalichie mem/kg API v testovom rantayme:
    # v proekte est neskolko alternativnykh registratorov, i ne vse sborki podnimayut /mem/kg/*.
    try:
        if not any(r.rule == "/mem/kg/upsert" for r in flask_app.url_map.iter_rules()):
            from routes.mem_kg_routes import register_mem_kg_routes

            register_mem_kg_routes(flask_app)
    except Exception:
        pass

    return flask_app


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


def _auth_header(client, role: str) -> dict[str, str]:
    r = client.post("/auth/login", json={"user": "pytest", "role": role})
    if r.status_code not in (200, 201):
        raise AssertionError(f"/auth/login failed for role={role}: {r.status_code}")
    data = r.get_json() or {}
    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        raise AssertionError(f"/auth/login returned no access_token for role={role}")
    return {"Authorization": f"Bearer {token}"}


def _auth_token(client, role: str) -> str:
    hdr = _auth_header(client, role)
    return hdr["Authorization"].split(" ", 1)[1]


@pytest.fixture
def auth_hdr_user(client):
    return _auth_header(client, "user")


@pytest.fixture
def auth_hdr_admin(client):
    return _auth_header(client, "admin")


@pytest.fixture
def auth_hdr_operator(client):
    return _auth_header(client, "operator")


@pytest.fixture
def auth_header(auth_hdr_admin):
    """Legacy alias used by older tests."""
    return auth_hdr_admin


@pytest.fixture
def admin_jwt(client):
    return _auth_token(client, "admin")


@pytest.fixture
def user_jwt(client):
    return _auth_token(client, "user")


@pytest.fixture
def operator_jwt(client):
    return _auth_token(client, "operator")
