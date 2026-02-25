# -*- coding: utf-8 -*-
"""routes/replication_routes.py - P2P-replikatsiya: streaming/snapshot/E2EE/rotatsiya klyuchey.

Registration (istoricheskiy kontrakt):
    from routes.replication_routes import register_replication_routes
    register_replication_routes(app, url_prefix="/replication")

Endpoint:
  GET /replication/stream?since=<ts>&limit=<n>&encrypt=0|1
       → JSON [{id,ts,kind,payload}, ...] ILI application/octet-stream (E2EE)
       Zagolovki: X-Node-Id, X-Key-Id (esli encrypt=1), X-Signature
  GET /replication/snapshot?encrypt=0|1
       → zip (JSON-fayly storadzhey) ILI zashifrovannyy blob; s subscribe
  POST /replication/rotate_keys → smena E2EE klyucha

Mosty:
- Yavnyy: (P2P ↔ Memory) potok sobytiy/snapshot dlya pervichnoy i inkrementalnoy sinkhronizatsii.
- Skrytyy #1: (Kriptografiya ↔ Arkhitektura) podpis (HMAC) i E2EE zagolovki obespechivayut doverie i tselostnost.
- Skrytyy #2: (Logika ↔ Kontrakty) determinirovannye zagolovki/tipy kontenta uproschayut payplayny.
- Skrytyy #3: (Audit ↔ Prozrachnost) uzlovye ID i time-marks podkhodyat dlya “profilea” sobytiy.

Zemnoy abzats:
Eto kak “kapelnitsa” dannykh mezhdu uzlami: potok (stream) - dlya postoyannogo podliva,
a snapshot - like “litrovaya banka” na zapuske. Podpisyvaem i, pri neobkhodimosti, shifruem taru."""
from __future__ import annotations

import io
import json
import os
import zipfile
from typing import Any, Dict, List, Tuple

from flask import Response, jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore

from modules import events_bus  # type: ignore
from security import e2ee  # type: ignore
from security.signing import get_hmac_key, header_signature  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    return base


def _node_id() -> str:
    return os.getenv("REPLICA_NODE_ID") or os.uname().nodename


def _sign_and_build(body: bytes, encrypt: bool) -> Response:
    sig = header_signature(body, key=get_hmac_key())
    headers = {
        "X-Node-Id": _node_id(),
        "X-Signature": sig,
    }
    if encrypt:
        headers["Content-Type"] = "application/octet-stream"
        headers["X-E2EE"] = "1"
        try:
            headers["X-Key-Id"] = e2ee.current_key_id()
        except Exception:
            headers["X-Key-Id"] = "unknown"
        return Response(body, headers=headers)
    else:
        headers["Content-Type"] = "application/json; charset=utf-8"
        return Response(body, headers=headers)


def _collect_snapshot_files() -> List[Tuple[str, str]]:
    """We collect useful storage files (existing).
    Returns a list of pairs (artznaime, abspath)"""
    base = _persist_dir()
    candidates = [
        ("knowledge_graph/nodes.json", os.path.join(base, "knowledge_graph", "nodes.json")),
        ("knowledge_graph/edges.json", os.path.join(base, "knowledge_graph", "edges.json")),
        ("hypotheses.json", os.path.join(base, "hypotheses.json")),
        ("structured_mem/store.json", os.path.join(base, "structured_mem", "store.json")),
        ("events/events.jsonl", os.path.join(base, "events", "events.jsonl")),
        ("telegram_feed/feed.jsonl", os.path.join(base, "telegram_feed", "feed.jsonl")),
        ("scheduler/tasks.json", os.path.join(base, "scheduler", "tasks.json")),
    ]
    out: List[Tuple[str, str]] = []
    for arc, path in candidates:
        if os.path.exists(path):
            out.append((arc, path))
    return out


def register_replication_routes(app, url_prefix: str = "/replication"):
    @app.get(f"{url_prefix}/stream")
    @jwt_required()
    def replication_stream():
        """Returns a slice of the event tape with a signature and optional E2EE."""
        try:
            since = float(request.args.get("since") or "0")
        except Exception:
            since = 0.0
        try:
            limit = max(1, min(int(request.args.get("limit", "500")), 2000))
        except Exception:
            limit = 500
        encrypt = bool(int(request.args.get("encrypt", "0") or 0))

        items = events_bus.feed(since=since, kind=None, limit=limit)  # type: ignore[attr-defined]
        payload = {
            "ok": True,
            "node_id": _node_id(),
            "since": since,
            "limit": limit,
            "items": items,
            "next_since": (items[-1]["ts"] if items else since),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if encrypt:
            try:
                _, blob = e2ee.encrypt_bytes(body)  # type: ignore[attr-defined]
            except Exception as e:
                return jsonify({"ok": False, "error": f"E2EE: {e}"}), 500
            return _sign_and_build(blob, encrypt=True)
        else:
            return _sign_and_build(body, encrypt=False)

    @app.get(f"{url_prefix}/snapshot")
    @jwt_required()
    def replication_snapshot():
        """Full data snapshot (zip) - for initial synchronization."""
        encrypt = bool(int(request.args.get("encrypt", "0") or 0))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for arc, path in _collect_snapshot_files():
                try:
                    zf.write(path, arcname=arc)
                except Exception:
                    continue
        raw = buf.getvalue()
        if encrypt:
            try:
                _, blob = e2ee.encrypt_bytes(raw)  # type: ignore[attr-defined]
            except Exception as e:
                return jsonify({"ok": False, "error": f"E2EE: {e}"}), 500
            return _sign_and_build(blob, encrypt=True)
        else:
            headers = {
                "Content-Type": "application/zip",
                "Content-Disposition": "attachment; filename=snapshot.zip",
                "X-Node-Id": _node_id(),
                "X-Signature": header_signature(raw, key=get_hmac_key()),
            }
            # Extension: synthesis of a snapshot with MultiLLMIIntegrator and sending to thinking
            if hasattr(app, "multi_llm"):
                try:
                    synth = app.multi_llm.synthesize("Snapshot of data for replication")
                    app.logger.info("Esther created a snapshot and thought: Data for archive, archive for synthesis!")
                    try:
                        from thinking.think_core import init_thinking  # type: ignore
                        init_thinking(synth)  # Send to thinking for thought
                    except Exception:
                        app.logger.warning("thinking ne nayden. Propuskaem razmyshleniya.")
                except Exception:
                    pass
            return Response(raw, headers=headers)

    @app.post(f"{url_prefix}/rotate_keys")
    @jwt_required()
    def replication_rotate_keys():
        """E2EE key rotation (locally). Returns old/new key ID."""
        try:
            out = e2ee.rotate_key()  # type: ignore[attr-defined]
            # Expansion: synthesis after rotation and sending to self-evo
            if hasattr(app, "multi_llm"):
                try:
                    synth = app.multi_llm.synthesize("Key rotation complete")
                    out["synth"] = synth
                    app.logger.info("Esther turned the keys and thought: New secrets for safety!")
                    try:
                        from selfevo.evo_engine import start_evolution  # type: ignore
                        start_evolution(json.dumps(out, ensure_ascii=False))
                    except Exception:
                        app.logger.warning("self-evo ne nayden. Propuskaem evolyutsiyu.")
                except Exception:
                    pass
            return jsonify(out)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500


__all__ = ["register_replication_routes"]
# c=a+b


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
def register(app):
    # calls an existing register_replication_rutes(app) (url_prefix is ​​taken by default inside the function)
    return register_replication_routes(app)

# === /AUTOSHIM ===