# -*- coding: utf-8 -*-
"""tests/nudges/test_nudges_engine.py - dymovoy test: sobytie → pending → outbox (dry-run).

MOSTY:
- (Yavnyy) Proveryaem planirovanie po AssignmentPlanned s dedlaynom v blizhayshie minuty.
- (Skrytyy #1) Mapping agent→contact i DEV_DRYRUN obespechivayut bezopasnuyu otpravku.
- (Skrytyy #2) Put: add_event → plan → enqueue → flush → outbox (via messaging.broadcast).

ZEMNOY ABZATs:
Pokazyvaet, chto “sobytie” realno privodit k izmerimoy otpravke (ili dryrun), ne lomaya ostalnuyu sistemu.

# c=a+b"""

from __future__ import annotations

import time

from nudges import store
from nudges.engine import plan as plan_nudges


def test_event_to_outbox(monkeypatch, tmp_path, anyio_backend):
    monkeypatch.setenv("MESSAGING_DB_PATH", str(tmp_path / "test_nudges.sqlite"))
    monkeypatch.setenv("DEV_DRYRUN", "1")  # bezopasno
    monkeypatch.delenv("NUDGES_SLA_CHAIN", raising=False)

    # mapping
    store.map_agent("pilot-1", "telegram:42")

    # event with deadline in 10 minutes
    now = time.time()
    payload = {
        "deadline_ts": now + 600,
        "actors": [{"agent_id": "pilot-1", "role": "operator"}],
        "summary": "dostavka",
    }
    ev_id = store.add_event("AssignmentPlanned", "task-42", now - 2, payload)
    ev = store.read_event(ev_id)
    plans = plan_nudges(ev)
    assert plans and plans[0]["key"] == "telegram:42"

    # postavit v ochered
    for p in plans:
        store.enqueue(ev_id, p["due_ts"], p["key"], p["kind"], p["intent"])

    # otpravit
    # simulates calling an endpoint manually (without FastAPI); just pull store.list_pending and use broadcast
    from messaging.broadcast import send_broadcast

    pend = store.list_pending(limit=100)
    keys = [p[4] for p in pend]
    res = send_broadcast(keys, pend[0][6], adapt_kind=pend[0][5])  # vozmem intent/kind pervoy zapisi
    assert "sent" in res
