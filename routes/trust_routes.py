# -*- coding: utf-8 -*-
"""routes/trust_routes.py - REST dlya upravleniya doveriem: lokalnyy klyuch, piry, priglasheniya Re podpisi.

Mosty:
- Yavnyy: (Beb v†" Goverie) CRUD-dostup k klyucham, piram, priglasheniyam Re podpisyam.
- Skrytyy #1: (Integratsiya v†" Middleware) ispolzuetsya integrity_guard dlya proverki podpisey.
- Skrytyy #2: (Bezopasnost v†" Kontrol) baziruetsya na modulyakh keystore, peers, invite.
- Skrytyy #3: (Release v†" Vekap) podpisi relizov vlivayutsya v manifest dlya tselostnosti.

Zemnoy abzats:
Polnyy nabor dlya doveriya: upravlyay klyuchami, opredelyay, “komu verim”,
vydavay i proveryay “kto razreshil”, stav i proveryay tsifrovye pechati.
Bse prosto, nadezhno Re v odnom meste.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Single Blueprint for all routes associated with the trust
bp_trust = Blueprint("trust", __name__)

try:
    # Functions for working with local identification
    from modules.trust.keystore import get_local_identity  # type: ignore
    # Functions for managing trusted peers
    from modules.trust.peers import list_peers, add_peer  # type: ignore
    # Functions for creating and validating invitations (tokens)
    from modules.trust.invite import issue as issue_invite, verify as verify_invite  # type: ignore
    # Functions for working with keys and digital signatures
    from modules.trust.sign import key_status, key_init, sign_path, verify_sig  # type: ignore
except Exception:
    # If no modules are found, all stub functions will be None
    get_local_identity = None  # type: ignore
    list_peers = add_peer = None  # type: ignore
    issue_invite = verify_invite = None  # type: ignore
    key_status = key_init = sign_path = verify_sig = None  # type: ignore

def register(app):
    """R egistriruet dannyy Blueprint v prilozhenii Flask."""
    app.register_blueprint(bp_trust)

# --- Routes for local identification ---

@bp_trust.route("/trust/local", methods=["GET"])
def api_local():
    """Returns local key/identity information."""
    if get_local_identity is None:
        return jsonify({"ok": False, "error": "keystore_unavailable"}), 500
    return jsonify({"ok": True, **get_local_identity()})

# --- Routes for managing trusted peers ---

@bp_trust.route("/trust/peers", methods=["GET"])
def api_peers():
    """Returns a list of trusted peers."""
    if list_peers is None:
        return jsonify({"ok": False, "error": "trust_store_unavailable"}), 500
    return jsonify({"ok": True, **list_peers()})

@bp_trust.route("/trust/peers/add", methods=["POST"])
def api_peers_add():
    """Dobavlyaet novogo doverennogo pira."""
    if add_peer is None:
        return jsonify({"ok": False, "error": "trust_store_unavailable"}), 500
    d = (request.get_json(True, True) or {})
    return jsonify(add_peer(str(d.get("id","")), str(d.get("name","")), str(d.get("alg","")), str(d.get("pubkey",""))))

# --- Routes for creating and checking invitations (tokens) ---

@bp_trust.route("/trust/invite/issue", methods=["POST"])
def api_inv_issue():
    """Sozdaet token-priglashenie."""
    if issue_invite is None:
        return jsonify({"ok": False, "error": "invite_unavailable"}), 500
    d = (request.get_json(True, True) or {})
    return jsonify(issue_invite(str(d.get("sub","")), str(d.get("scope","")), int(d.get("ttl_sec",600)), d.get("archive_sha"), str(d.get("aud","local"))))

@bp_trust.route("/trust/invite/verify", methods=["POST"])
def api_inv_verify():
    """Checks the invitation token."""
    if verify_invite is None:
        return jsonify({"ok": False, "error": "invite_unavailable"}), 500
    d = (request.get_json(True, True) or {})
    tok = d.get("token") or d  # dopuskaem pryamuyu otpravku tokena
    return jsonify(verify_invite(tok))

# --- Routes for signing key management ---

@bp_trust.route("/trust/key/status", methods=["GET"])
def api_key_status():
    """Returns the status of the local signing key."""
    if key_status is None:
        return jsonify({"ok": False, "error": "trust_sign_unavailable"}), 500
    return jsonify(key_status())

@bp_trust.route("/trust/key/init", methods=["POST"])
def api_key_init():
    """Initializes (creates) a new signing key."""
    if key_init is None:
        return jsonify({"ok": False, "error": "trust_sign_unavailable"}), 500
    return jsonify(key_init())

# --- Routes for creating and verifying digital signatures ---

@bp_trust.route("/trust/sign", methods=["POST"])
def api_sign():
    """Create a digital signature for the specified path."""
    if sign_path is None:
        return jsonify({"ok": False, "error": "trust_sign_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(sign_path(str(d.get("path", ""))))

@bp_trust.route("/trust/verify", methods=["POST"])
def api_verify_sig():
    """Verifies the digital signature."""
    if verify_sig is None:
        return jsonify({"ok": False, "error": "trust_sign_unavailable"}), 500
    d = request.get_json(True, True) or {}
# return jsonify(verify_sig(d))
