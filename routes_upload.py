# -*- coding: utf-8 -*-
from __future__ import annotations

"""
routes/routes_upload.py — zagruzka faylov cherez API dlya ingest/RAG.

Endpointy (po umolchaniyu url_prefix="/ingest"):
- POST /ingest/file   (multipart/form-data, pole "file")
- GET  /ingest/status?id=...

Povedenie:
- Kartinki zaprescheny (deny-list rasshireniy).
- Limit razmera: MAX_UPLOAD_MB (env, po umolchaniyu 25MB).
- Esli est app.ingest: submit_file(tmp_path) → {"id": job_id, "status":"QUEUED"}
- Esli ingest net, no est vstore: chitaem tekst (utf-8 ignore) i kladem v vstore → DONE
- Esli net ni ingest, ni vstore: sokhranyaem fayl v inbox i vozvraschaem STORED (ne padaem)

Sovmestimost:
- Signatura register_upload_routes(app, vstore, memory_manager, url_prefix="/ingest") sokhranena
  (memory_manager poka ispolzuetsya best-effort: mozhno dopolnit, no etot rout ne dolzhen lomatsya
  iz-za razlichiy versiy).
"""

import logging
import os
import uuid
from typing import Any, Dict, Optional, Tuple

from flask import jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)

# Yavnyy deny-list kartinok
IMAGE_DENY = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg"}

# Limit fayla (MB)
try:
    MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
except Exception:
    MAX_MB = 25
MAX_MB = max(1, MAX_MB)


def _ext_ok(name: str) -> bool:
    ext = os.path.splitext(name)[1].lower()
    # zapreschaem izobrazheniya, vse ostalnoe propuskaem v konveyer
    return ext not in IMAGE_DENY


def _safe_basename(filename: str) -> str:
    # Werkzeug uzhe daet chto-to adekvatnoe, no my usilim: vyrezhem puti
    return os.path.basename(filename or "").strip() or "file.bin"


def _get_file_size_bytes(f) -> Optional[int]:
    """
    Nadezhno poluchit razmer fayla iz werkzeug FileStorage.
    Vozvraschaet None, esli opredelit nevozmozhno.
    """
    # 1) content_length (mozhet byt None)
    try:
        cl = getattr(f, "content_length", None)
        if cl is not None:
            return int(cl)
    except Exception:
        pass

    # 2) stream seek/tell
    try:
        stream = getattr(f, "stream", None)
        if stream is None:
            return None
        cur = stream.tell()
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(cur)
        return int(size)
    except Exception:
        return None


def _vstore_add_text(vstore, text: str, meta: Dict[str, Any]) -> None:
    """
    Best-effort: podderzhivaem raznye signatury add_texts (Chroma-podobnye) ili add.
    """
    if vstore is None:
        return

    # add_texts(texts, metadatas=[...]) — samyy chastyy variant
    if hasattr(vstore, "add_texts") and callable(getattr(vstore, "add_texts")):
        try:
            vstore.add_texts([text], metadatas=[meta])  # type: ignore[attr-defined]
            return
        except TypeError:
            # nekotorye realizatsii prinimayut meta=
            vstore.add_texts([text], meta=meta)  # type: ignore[attr-defined]
            return

    if hasattr(vstore, "add") and callable(getattr(vstore, "add")):
        vstore.add(text, meta)  # type: ignore[attr-defined]


def register_upload_routes(app, vstore, memory_manager, url_prefix: str = "/ingest"):
    """
    Realizuet:
      POST /ingest/file
      GET  /ingest/status?id=

    inbox_dir: gde vremenno skladiruem fayly do obrabotki ingest-menedzherom.
    """
    # Esli u vstore est persist_dir — ispolzuem ego; inache cwd.
    base_dir = getattr(getattr(app, "vstore", None), "persist_dir", None) or os.getcwd()
    inbox_dir = os.path.join(base_dir, "inbox")
    os.makedirs(inbox_dir, exist_ok=True)

    @app.post(url_prefix + "/file")
    @jwt_required()
    def upload_file():
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "no file"}), 400

        f = request.files["file"]
        filename = _safe_basename(getattr(f, "filename", ""))

        if not filename:
            return jsonify({"ok": False, "error": "empty filename"}), 400

        if not _ext_ok(filename):
            return jsonify({"ok": False, "error": "unsupported media type"}), 415

        size = _get_file_size_bytes(f)
        if size is not None and size > MAX_MB * 1024 * 1024:
            return jsonify({"ok": False, "error": "too large", "max_mb": MAX_MB}), 413

        # Sokhranyaem vo vremennyy fayl v inbox_dir
        tmp_name = f"{uuid.uuid4().hex}_{filename}"
        tmp_path = os.path.join(inbox_dir, tmp_name)

        try:
            f.save(tmp_path)
        except Exception as e:
            log.exception("upload save failed")
            return jsonify({"ok": False, "error": f"save_failed: {e}"}), 500

        # ingest prioriteten
        ingest = getattr(app, "ingest", None)
        if ingest is not None:
            try:
                job_id = ingest.submit_file(tmp_path)  # type: ignore[attr-defined]
                return jsonify({"ok": True, "id": job_id, "status": "QUEUED"}), 200
            except Exception as e:
                # Vazhno: ne teryaem fayl. On uzhe v inbox_dir.
                log.exception("ingest.submit_file failed; file kept in inbox")
                return jsonify(
                    {
                        "ok": False,
                        "id": "stored",
                        "status": "STORED",
                        "error": f"ingest_failed: {e}",
                        "note": "file saved to inbox; ingest submission failed",
                    }
                ), 202

        # vstore fallback: pytaemsya izvlech tekst i srazu proindeksirovat
        if vstore is not None:
            try:
                with open(tmp_path, "rb") as rf:
                    data = rf.read()
                text = data.decode("utf-8", errors="ignore").strip()

                if text:
                    meta = {"source": filename, "filename": filename, "path": tmp_name}
                    _vstore_add_text(vstore, text, meta)

                    # best-effort: mozhno dobavit v structured pamyat kak «ingest-sled»
                    try:
                        if memory_manager is not None and hasattr(memory_manager, "add_to_medium_term"):
                            memory_manager.add_to_medium_term("*", {"text": text, "tags": ["ingest"], "weight": 0.6})
                    except Exception:
                        pass

                    return jsonify({"ok": True, "id": "direct", "status": "DONE"}), 200

                return jsonify({"ok": True, "id": "stored", "status": "STORED", "note": "file is not text"}), 200

            except Exception as e:
                log.exception("vstore fallback failed; file kept in inbox")
                return jsonify({"ok": False, "error": f"fallback_failed: {e}", "status": "STORED"}), 202

        # posledniy variant — prosto sokhranit
        return jsonify({"ok": True, "id": "stored", "status": "STORED", "note": "no ingest/vstore; file saved to inbox"}), 200

    @app.get(url_prefix + "/status")
    @jwt_required()
    def upload_status():
        job_id = (request.args.get("id", "") or "").strip()
        if not job_id:
            return jsonify({"ok": False, "error": "id required"}), 400

        ingest = getattr(app, "ingest", None)
        if ingest is None:
            return jsonify({"ok": False, "error": "ingest manager not available"}), 503

        # Sovmestimost: raznye realizatsii mogut imet get_job(id) ili list_jobs()
        try:
            if hasattr(ingest, "get_job") and callable(getattr(ingest, "get_job")):
                j = ingest.get_job(job_id)  # type: ignore[attr-defined]
                if j:
                    return jsonify({"ok": True, "job": j}), 200
                return jsonify({"ok": False, "error": "not found"}), 404

            jobs = ingest.list_jobs()  # type: ignore[attr-defined]
            for j in jobs or []:
                if isinstance(j, dict) and j.get("id") == job_id:
                    return jsonify({"ok": True, "job": j}), 200
            return jsonify({"ok": False, "error": "not found"}), 404

        except Exception as e:
            log.exception("upload_status failed")
            return jsonify({"ok": False, "error": f"list_failed: {e}"}), 500