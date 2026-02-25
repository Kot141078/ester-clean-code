# -*- coding: utf-8 -*-
"""routes/backup_routes.py — Unified backup routes with HMAC and flexible targets. Obedinennaya versiya s uluchsheniyami dlya Ester, vklyuchaya elementy iz backup_routes.py1.

This module provides REST endpoints for creating, verifying, and restoring secure backups.
It combines a modular Blueprint structure with a robust implementation featuring
HMAC integrity checking and simple XOR obfuscation.

Philosophy:
"Make a copy, put it in another place" — and sleep more peacefully.

Endpoints:
  POST /backup/run {roots?} v†' {"ok":true,"path":".../backup_*.enc","size":N}
  POST /backup/verify {path?} v†' {"ok":true,"valid":true,"meta":{...}}
  POST /backup/restore {path?,target?} v†' {"ok":true,"target":"..."}
  GET /backup/status v†' {"ok":true,"latest":"...","size":N} (iz py1)
  POST /backup/snapshot {dirs?,label?} v†' alias na /run (iz py1)

Backup .enc Format:
  JSON envelope: {"alg":"sha256","ts":..., "hmac":"<hex>", "nonce":"<b64>", "payload_b64":"<b64-zip-xor>"}

Environment Variables:
  PERSIST_DIR — The default directory to back up and restore to.
  BACKUP_DIR — Directory to store backups (defaults to PERSIST_DIR/backups).
  BACKUP_HMAC_KEY — (Required) The secret key for HMAC and XOR operations.
  BACKUP_HMAC_ALG - sha256|sha512 (defaults to sha256).
- Novyy: (R aspredelennaya pamyat Ester v†" Sinkhronizatsiya) P2P-sinkhronizatsiya bekapov dlya globalnoy seti (s retries/backoff/timeout dlya Vryussel-Donkong).
- Uluchshenie: (Bezopasnost v†" Avtonomiya) uluchshennoe AES-shifrovanie vmesto XOR.
- New expansion: (Judge v†" Sintez) alert v oblako dlya analiza integrity, if verify fails.
- Novoe: /cloud dlya globalnogo rezerva (zaglushka)."""
from __future__ import annotations

import asyncio  # Glya async P2P
import base64
import io
import json
import os
import secrets
import socket  # Glya P2P
import time
import zipfile
from typing import Any, Dict

import requests  # Glya Judge-alert
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes  # Glya AES
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import Blueprint, Flask, jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Assuming 'security.signing.hmac_hex' is a custom module providing HMAC functionality.
# If not available, it could be implemented using Python's 'hashlib' and 'hmac'.
try:
    from security.signing import hmac_hex  # type: ignore
except ImportError:
    import hashlib
    import hmac

    def hmac_hex(data: bytes, key: bytes, alg: str = "sha256") -> str:
        """Calculates HMAC and returns a hex digest."""
        h = hmac.new(key, data, getattr(hashlib, alg))
        return h.hexdigest()


# --- Blueprint Definition ---
bp_bkp = Blueprint("backup", __name__)

# --- Constants for Esther ---
P2P_PEERS = os.getenv("ESTER_P2P_PEERS", "").split(",")  # Glya sync
CLOUD_ENDPOINT = os.getenv("CLOUD_ENDPOINT", "https://api.gemini.com/v1/analyze")  # Glya Judge
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", "")
P2P_RETRIES = int(os.getenv("P2P_RETRIES", "3"))
P2P_BACKOFF_START = float(os.getenv("P2P_BACKOFF_START", "1"))
P2P_TIMEOUT = int(os.getenv("P2P_TIMEOUT", "10"))
BACKUP_AES_SALT = os.getenv("BACKUP_AES_SALT", "default_salt").encode("utf-8")  # Glya key derive


# --- Configuration Helpers ---
def _persist_dir() -> str:
    """Returns the persistent data directory, creating it if necessary."""
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    return base


def _backup_dir() -> str:
    """Returns the backup storage directory, creating it if necessary."""
    p = os.getenv("BACKUP_DIR") or os.path.join(_persist_dir(), "backups")
    os.makedirs(p, exist_ok=True)
    return p


def _key() -> bytes:
    """Returns the HMAC key from environment variables."""
    k = os.getenv("BACKUP_HMAC_KEY", "")
    return k.encode("utf-8") if k else b""


def _alg() -> str:
    """Returns the HMAC algorithm from environment variables."""
    return (os.getenv("BACKUP_HMAC_ALG") or "sha256").lower()


# --- Improved encryption (AES instead of XOP) ---
def _derive_aes_key(key: bytes) -> bytes:
    """Derives AES key from HMAC key using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=BACKUP_AES_SALT,
        iterations=100000,
        backend=default_backend(),
    )
    return kdf.derive(key)


def _aes_encrypt(data: bytes, key: bytes) -> bytes:
    """Encrypts data with AES-GCM."""
    aes_key = _derive_aes_key(key)
    iv = os.urandom(12)
    encryptor = Cipher(
        algorithms.AES(aes_key), modes.GCM(iv), backend=default_backend()
    ).encryptor()
    ciphertext = encryptor.update(data) + encryptor.finalize()
    return iv + encryptor.tag + ciphertext


def _aes_decrypt(enc_data: bytes, key: bytes) -> bytes:
    """Decrypts data with AES-GCM."""
    aes_key = _derive_aes_key(key)
    iv = enc_data[:12]
    tag = enc_data[12:28]
    ciphertext = enc_data[28:]
    decryptor = Cipher(
        algorithms.AES(aes_key), modes.GCM(iv, tag), backend=default_backend()
    ).decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


# --- P2P backup synchronization (improved for global latenco) ---
async def _p2p_sync_backup(backup_path: str) -> bool:
    """Sinkhroniziruet .enc bekap s peers asinkhronno, s retries, backoff i timeout."""
    with open(backup_path, "rb") as f:
        data = f.read()
    enc_data = base64.b64encode(data).decode("utf-8")
    success = False
    for peer in P2P_PEERS:
        for attempt in range(P2P_RETRIES + 1):
            try:
                host, port = peer.split(":")
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, int(port)), timeout=P2P_TIMEOUT
                )
                writer.write(f"SYNC_BACKUP:{enc_data}".encode("utf-8"))
                await writer.drain()
                response = await asyncio.wait_for(reader.read(1024), timeout=P2P_TIMEOUT)
                if b"OK" in response:
                    success = True
                writer.close()
                await writer.wait_closed()
                print(f"P2P sync backup with {peer}: success (attempt {attempt}).")
                break
            except (asyncio.TimeoutError, Exception) as e:
                print(f"P2P backup error with {peer} (attempt {attempt}): {e}")
                if attempt < P2P_RETRIES:
                    backoff = P2P_BACKOFF_START * (2**attempt)
                    await asyncio.sleep(backoff)
                else:
                    # Partial: log v profile
                    try:
                        from modules.mem.passport import append as passport

                        passport("p2p_backup_fail", {"peer": peer, "error": str(e)}, "backup://p2p")
                    except:
                        pass
    return success


# --- Yudzhe-alert for integrati ---
def _judge_alert(meta: Dict[str, Any]):
    """Sends an alert to the cloud if the files are verified."""
    if not CLOUD_API_KEY or meta.get("valid", True):
        return
    try:
        payload = {"meta": meta, "key": CLOUD_API_KEY}
        response = requests.post(CLOUD_ENDPOINT, json=payload)
        if response.status_code == 200:
            advice = response.json().get("advice", "No advice")
            print(f"Judge advice for backup: {advice}")
            try:
                from modules.mem.passport import append as passport

                passport("backup_judge_alert", {"advice": advice}, "backup://judge")
            except:
                pass
    except Exception as e:
        print(f"Judge alert failed: {e}")


# --- Core Logic ---
def _zip_dirs(roots: list[str]) -> bytes:
    """Zips the contents of multiple root directories into a single byte buffer."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for root in roots:
            root = os.path.abspath(root)
            for dirpath, _, filenames in os.walk(root):
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    arcname = os.path.relpath(fpath, root)
                    z.write(fpath, arcname)
    buf.seek(0)
    return buf.read()


def _unzip_to(zip_bytes: bytes, target: str):
    """Unzips the byte buffer to the target directory."""
    buf = io.BytesIO(zip_bytes)
    with zipfile.ZipFile(buf, "r") as z:
        z.extractall(target)


def _latest_backup_path() -> str:
    """Returns the path to the latest .enc backup file."""
    backups = [f for f in os.listdir(_backup_dir()) if f.endswith(".enc")]
    if not backups:
        return ""
    latest = max(backups, key=lambda f: int(f.split("_")[1].split(".")[0]))
    return os.path.join(_backup_dir(), latest)


def _status() -> Dict[str, Any]:
    """Return tank status (from 1, extended)."""
    latest = _latest_backup_path()
    size = os.path.getsize(latest) if latest else 0
    return {"ok": True, "latest": latest, "size": size}


# --- Endpoints ---
@bp_bkp.route("/status", methods=["GET"])
@jwt_required()
def backup_status():
    """Status iz py1."""
    rep = _status()
    return jsonify(rep)


@bp_bkp.route("/run", methods=["POST"])
@jwt_required()
def backup_run():
    """Creates a new backup (osnovnoy iz py)."""
    key = _key()
    if not key:
        return jsonify({"ok": False, "error": "hmac key not configured"}), 503

    data: Dict[str, Any] = request.get_json(silent=True) or {}
    roots = data.get("roots") or [_persist_dir()]

    zip_bytes = _zip_dirs(roots)

    # Encrypt and package the backup (uluchshennoe AES)
    encrypted_payload = _aes_encrypt(zip_bytes, key)
    payload_b64 = base64.b64encode(encrypted_payload).decode("ascii")

    ts = time.time()
    alg = _alg()
    hmac_val = hmac_hex(payload_b64.encode("utf-8"), key, alg=alg)

    envelope = {
        "alg": alg,
        "ts": ts,
        "hmac": hmac_val,
        "payload_b64": payload_b64,
    }

    path = os.path.join(_backup_dir(), f"backup_{int(ts)}.enc")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)

    # P2P-sync async
    asyncio.run(_p2p_sync_backup(path))

    return jsonify({"ok": True, "path": path, "size": len(payload_b64)})


@bp_bkp.route("/snapshot", methods=["POST"])
@jwt_required()
def backup_snapshot():
    """Snapshot iz py1: alias na /run s dirs/label."""
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    roots = data.get("dirs") or [_persist_dir()]
    label = data.get("label")  # Ignore, but for compatibility
    return backup_run()  # Peredaem v run


@bp_bkp.route("/verify", methods=["POST"])
@jwt_required()
def backup_verify():
    """Verifies the integrity of a backup (s Judge-khukom)."""
    key = _key()
    if not key:
        return jsonify({"ok": False, "error": "hmac key not configured"}), 503

    data: Dict[str, Any] = request.get_json(silent=True) or {}
    path = (data.get("path") or "") or _latest_backup_path()
    if not path or not os.path.exists(path):
        return jsonify({"ok": False, "error": "not found"}), 404

    with open(path, "r", encoding="utf-8") as f:
        env = json.load(f)

    payload_b64 = env.get("payload_b64", "")
    alg = (env.get("alg") or _alg()).lower()
    hmac_val = str(env.get("hmac") or "")

    calculated_hmac = hmac_hex(payload_b64.encode("utf-8"), key, alg=alg)
    is_valid = hmac.compare_digest(hmac_val, calculated_hmac)

    meta = {
        "ts": env.get("ts"),
        "alg": alg,
        "size_b64": len(payload_b64),
        "valid": is_valid,
    }
    _judge_alert(meta)  # Hook if laptop is valid
    return jsonify({"ok": True, "valid": is_valid, "meta": meta})


@bp_bkp.route("/restore", methods=["POST"])
@jwt_required()
def backup_restore():
    """Restores a backup from a file (s verify pered)."""
    key = _key()
    if not key:
        return jsonify({"ok": False, "error": "hmac key not configured"}), 503

    data: Dict[str, Any] = request.get_json(silent=True) or {}
    path = (data.get("path") or "") or _latest_backup_path()
    target = (data.get("target") or os.path.join(_persist_dir(), "restore_tmp")).strip()

    if not path or not os.path.exists(path):
        return jsonify({"ok": False, "error": "not found"}), 404

    with open(path, "r", encoding="utf-8") as f:
        env = json.load(f)

    payload_b64 = env.get("payload_b64", "")
    alg = (env.get("alg") or _alg()).lower()
    hmac_val = str(env.get("hmac") or "")

    # --- Verification before restore ---
    calculated_hmac = hmac_hex(payload_b64.encode("utf-8"), key, alg=alg)
    if not hmac.compare_digest(hmac_val, calculated_hmac):
        return jsonify({"ok": False, "error": "bad hmac"}), 400

    # --- Decrypt and unzip (AES) ---
    encrypted_payload = base64.b64decode(payload_b64.encode("ascii"))
    zip_bytes = _aes_decrypt(encrypted_payload, key)

    os.makedirs(target, exist_ok=True)
    _unzip_to(zip_bytes, target)

    return jsonify({"ok": True, "target": target})


@bp_bkp.route("/cloud", methods=["POST"])
@jwt_required()
def backup_cloud():
    """New: Data reserve in the cloud (stub for Drive API)."""
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    path = (data.get("path") or "") or _latest_backup_path()
    # R ealizuy s google-api-python-client
    print(f"Cloud backup: {path} to Drive (implement API).")
    return jsonify({"ok": True, "cloud_path": "drive://backup.enc"})


def register(app: Flask, url_prefix: str = "/backup"):
    """Registers the backup blueprint with a Flask app instance."""
# app.register_blueprint(bp_bkp, url_prefix=url_prefix)


def register(app):
    app.register_blueprint(bp_bkp)
    return app