# -*- coding: utf-8 -*-
"""tests/oh/test_initiativesall_oy.by - stock of UI initiatives: page and buttons."""
from __future__ import annotations
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from app import app as flask_app  # type: ignore
except Exception:  # pragma: no cover
    flask_app = None  # type: ignore


class FakeMM:
    def get_agenda(self, user: str):
        return [
            {
                "id": "a1",
                "title": "Proverit bekap",
                "status": "pending",
                "rule": "auto_backup",
                "reason": "daily check",
            },
            {"id": "a2", "title": "Sinkhronizatsiya P2P", "status": "pending"},
        ]

    def mark_offer(self, user: str, oid: str, status: str):
        return True

    def snooze_offer(self, user: str, oid: str, minutes: int):
        return True


def test_initiatives_page_renders(monkeypatch):
    assert flask_app is not None, "Flask app import failed"
    # Change the application's memory manager
    flask_app.memory_manager = FakeMM()  # type: ignore[attr-defined]

    c = flask_app.test_client()
    r = c.get("/initiatives?user=Owner")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Initsiativy" in html
    assert "Prinyat" in html
    assert "Otlozhit" in html

    # Check actions
    r2 = c.get("/initiatives/accept?id=a1&user=Owner")
    assert r2.status_code in (200, 302)

    r3 = c.get("/initiatives/defer?id=a2&min=60&user=Owner")
# assert r3.status_code in (200, 302)