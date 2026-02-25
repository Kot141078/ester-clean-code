# -*- coding: utf-8 -*-
"""routes/ingest_routes.py - REST-ruchki dlya Ingest 2.0 (OCR/ASR/Caption/Code/Dedup/Batch).
Registration:
  from routes.ingest_routes import register_ingest_routes
  register_ingest_routes(app, url_prefix="/ingest")

All the best for JWT (kak i prochie). Nikakikh izmeneniy suschestvuyuschikh putey - eto novye endpoints."""
from __future__ import annotations

import base64
import io
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from flask import jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore

from modules.ingest.asr_engine import asr_transcribe  # type: ignore
from modules.ingest.code_ingest import ingest_code  # type: ignore
from modules.ingest.common import persist_dir, save_bytes, sha256_bytes, sha256_file, sniff_mime  # type: ignore
from modules.ingest.dedup_index import link_duplicate, record_ingest, should_ingest  # type: ignore
from modules.ingest.image_captioning import caption_image  # type: ignore
from modules.ingest.ocr_engine import run_ocr  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _read_upload_bytes() -> Tuple[str, bytes]:
    """Universal login parser:
      - multipart form-date: fillet=<binary>
      - ZhSION: ZZF0Z (data_b64 - beat64)"""
    if request.files:
        f = next(iter(request.files.values()))
        return f.filename, f.read()
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "upload.bin")
    b64 = data.get("data_b64")
    if not b64:
        raise ValueError("Ozhidaetsya fayl (multipart) ili data_b64 v JSON.")
    try:
        raw = base64.b64decode(b64)
    except Exception as e:
        raise ValueError("Nevalidnyy base64: " + str(e))
    return name, raw


def register_ingest_routes(app, url_prefix: str = "/ingest"):
    elon_mode = os.getenv("ELON_MODE", "false").lower() == "true"

    # -------- OCR --------
    @app.post(f"{url_prefix}/ocr")
    @jwt_required()
    def ingest_ocr():
        try:
            lang = str((request.form.get("lang") or request.args.get("lang") or "eng+rus"))
            name, data = _read_upload_bytes()
            # Dedup before hard work
            sha = sha256_bytes(data)
            if not should_ingest(sha, size=len(data)):
                rec = record_ingest(
                    sha,
                    "(upload)",
                    size=len(data),
                    meta={"mime": "unknown", "hints": ["duplicate"]},
                )
                return jsonify({"ok": True, "duplicate": True, "dedup": rec})
            res = run_ocr(name, data, lang=lang, tags=["ingest"])
            record_ingest(
                sha,
                res["path"],
                size=len(data),
                meta={"mime": res["mime"], "hints": ["ocr"]},
            )
            # Extension: synthesis with MultiLLMIIntegrator
            if hasattr(app, "multi_llm"):
                synth = app.multi_llm.synthesize(res["text"])
                res["synth"] = synth if not elon_mode else f"Derzkiy OCR-sintez v dukhe Ilona: {synth}"
                app.logger.info("Esther saw the OCD text and thought: Wow, knowledge for the mind! Synthesis ready")
            # Integratsiya s self-evo i thinking
            try:
                from selfevo.evo_engine import start_evolution  # type: ignore
                from thinking.think_core import init_thinking  # type: ignore
                start_evolution(res["text"])  # Evolyutsiya
                init_thinking(res["text"])  # Razmyshleniya
                app.logger.info("Ester evolyutsionirovala i podumala nad OCR.")
            except ImportError as e:
                app.logger.warning(f"self-evo/thinking ne naydeny: {e}. Propuskaem.")
            return jsonify(res)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        finally:
            app.logger.info("OCD processing complete, Esther is ready for the next one.")

    # -------- ASR --------
    @app.post(f"{url_prefix}/asr")
    @jwt_required()
    def ingest_asr():
        try:
            lang = str((request.form.get("lang") or request.args.get("lang") or "ru"))
            name, data = _read_upload_bytes()
            sha = sha256_bytes(data)
            if not should_ingest(sha, size=len(data)):
                rec = record_ingest(
                    sha,
                    "(upload)",
                    size=len(data),
                    meta={"mime": "audio/wav", "hints": ["duplicate"]},
                )
                return jsonify({"ok": True, "duplicate": True, "dedup": rec})
            res = asr_transcribe(name, data, lang=lang)
            record_ingest(
                sha,
                res["path"],
                size=len(data),
                meta={"mime": res["mime"], "hints": ["asr"]},
            )
            # Extension: synthesis with MultiLLMIIntegrator
            if hasattr(app, "multi_llm"):
                synth = app.multi_llm.synthesize(res["text"])
                res["synth"] = synth if not elon_mode else f"Derzkiy ASR-sintez v dukhe Ilona: {synth}"
                app.logger.info("Esther heard the speech and thought: “Sound into text, text into mind!” Synthesis ready")
            # Integratsiya s self-evo i thinking
            try:
                from selfevo.evo_engine import start_evolution  # type: ignore
                from thinking.think_core import init_thinking  # type: ignore
                start_evolution(res["text"])  # Evolyutsiya
                init_thinking(res["text"])  # Razmyshleniya
                app.logger.info("Ester evolyutsionirovala i podumala nad ASR.")
            except ImportError as e:
                app.logger.warning(f"self-evo/thinking ne naydeny: {e}. Propuskaem.")
            return jsonify(res)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        finally:
            app.logger.info("ACP treatment complete, Esther is ready for the next one.")

    # -------- Image Caption --------
    @app.post(f"{url_prefix}/caption")
    @jwt_required()
    def ingest_caption():
        try:
            name, data = _read_upload_bytes()
            sha = sha256_bytes(data)
            if not should_ingest(sha, size=len(data)):
                rec = record_ingest(
                    sha,
                    "(upload)",
                    size=len(data),
                    meta={"mime": "image/*", "hints": ["duplicate"]},
                )
                return jsonify({"ok": True, "duplicate": True, "dedup": rec})
            res = caption_image(name, data)
            record_ingest(
                sha,
                res.get("path") or name,
                size=len(data),
                meta={"mime": res["mime"], "hints": ["caption"]},
            )
            # Extension: synthesis with MultiLLMIIntegrator
            if hasattr(app, "multi_llm"):
                synth = app.multi_llm.synthesize(res["caption"])
                res["synth"] = synth if not elon_mode else f"Derzkiy caption-sintez v dukhe Ilona: {synth}"
                app.logger.info("Esther saw the picture and thought: “Image into words, words into knowledge!” Synthesis ready")
            # Integratsiya s self-evo i thinking
            try:
                from selfevo.evo_engine import start_evolution  # type: ignore
                from thinking.think_core import init_thinking  # type: ignore
                start_evolution(res["caption"])  # Evolyutsiya
                init_thinking(res["caption"])  # Razmyshleniya
                app.logger.info("Ester evolyutsionirovala i podumala nad caption.")
            except ImportError as e:
                app.logger.warning(f"self-evo/thinking ne naydeny: {e}. Propuskaem.")
            return jsonify(res)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        finally:
            app.logger.info("Caption processing completed, Esther is ready for the next one.")

    # -------- Code --------
    @app.post(f"{url_prefix}/code")
    @jwt_required()
    def ingest_code_route():
        """
        JSON: {"root": "/abs/path/or/relative/to/PERSIST_DIR"}
        """
        data = request.get_json(silent=True) or {}
        root = str(data.get("root") or "").strip()
        if not root:
            return jsonify({"ok": False, "error": "root required"}), 400
        if not os.path.isabs(root):
            root = os.path.join(persist_dir(), root)
        if not os.path.isdir(root):
            return jsonify({"ok": False, "error": "root not found"}), 400
        try:
            res = ingest_code(root)
            # Extension: synthesis with MultiLLMIIntegrator
            if hasattr(app, "multi_llm"):
                synth = app.multi_llm.synthesize(json.dumps(res))
                res["synth"] = synth if not elon_mode else f"Derzkiy code-sintez v dukhe Ilona: {synth}"
                app.logger.info("Esther swallowed the code and thought: Code into knowledge, knowledge into evolution! Synthesis ready")
            # Integratsiya s self-evo i thinking
            try:
                from selfevo.evo_engine import start_evolution  # type: ignore
                from thinking.think_core import init_thinking  # type: ignore
                start_evolution(json.dumps(res))  # Evolyutsiya
                init_thinking(json.dumps(res))  # Razmyshleniya
                app.logger.info("Ester evolyutsionirovala i podumala nad kodom.")
            except ImportError as e:
                app.logger.warning(f"self-evo/thinking ne naydeny: {e}. Propuskaem.")
            return jsonify(res)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
        finally:
            app.logger.info("Code processing complete, Esther is ready for the next one.")

    # -------- Dedup status --------
    @app.post(f"{url_prefix}/dedup_check")
    @jwt_required()
    def ingest_dedup_check():
        """Checking a file for a duplicate without writing:
        - multipart: fillet
        - ZhSION: ZZF0Z"""
        try:
            name, data = _read_upload_bytes()
            sha = sha256_bytes(data)
            dup = not should_ingest(sha, size=len(data))
            return jsonify({"ok": True, "duplicate": dup, "sha256": sha})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        finally:
            app.logger.info("Dedup-chesk is completed, Esther is ready for the next one.")

    # -------- Bulk dir (PDF/TXT/MD/IMG) --------
    @app.post(f"{url_prefix}/scan_dir")
    @jwt_required()
    def ingest_scan_dir():
        """
        JSON: {"dir": "relative/or/abs/path", "mode":"text|ocr|caption", "glob":"*.pdf", "lang":"eng+rus"}
        """
        data = request.get_json(silent=True) or {}
        root = str(data.get("dir") or "").strip()
        mode = str(data.get("mode") or "text")
        pattern = str(data.get("glob") or "*")
        lang = str(data.get("lang") or "eng+rus")
        if not root:
            return jsonify({"ok": False, "error": "dir required"}), 400
        if not os.path.isabs(root):
            root = os.path.join(persist_dir(), root)
        if not os.path.isdir(root):
            return jsonify({"ok": False, "error": "dir not found"}), 400

        import fnmatch

        processed, skipped = 0, 0
        errors: List[Dict[str, Any]] = []
        results: List[Dict[str, Any]] = []
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if not fnmatch.fnmatch(fn, pattern):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, "rb") as f:
                        data_b = f.read()
                    sha = sha256_bytes(data_b)
                    if not should_ingest(sha, size=len(data_b)):
                        skipped += 1
                        continue
                    if mode == "caption":
                        res = caption_image(fn, data_b)
                    elif mode == "ocr":
                        res = run_ocr(fn, data_b, lang=lang, tags=["bulk"])
                    else:
                        # "text": probuem rasparsit PDF tekstom libo chitaem plaintext
                        mime = sniff_mime(path)
                        if mime == "application/pdf":
                            from modules.ingest.common import pdf_text_extract  # type: ignore

                            text = pdf_text_extract(data_b)
                        else:
                            text = open(path, "r", encoding="utf-8", errors="ignore").read()
                        if not text.strip():
                            continue
                        from modules.ingest.common import add_structured_record, kg_attach_artifact  # type: ignore

                        rid = add_structured_record(text=text[:2000], tags=["bulk", "text"])
                        kg_attach_artifact(label=fn, text=text, tags=["bulk", "text"])
                        res = {"ok": True, "path": path, "mime": mime, "record_id": rid, "text": text[:5000]}
                    record_ingest(
                        sha,
                        res.get("path") or path,
                        size=len(data_b),
                        meta={"hints": [mode]},
                    )
                    # Extension: synthesis with MultiLLMIIntegrator
                    if hasattr(app, "multi_llm") and "text" in res:
                        synth = app.multi_llm.synthesize(res["text"])
                        res["synth"] = synth if not elon_mode else f"Derzkiy bulk-sintez v dukhe Ilona: {synth}"
                        app.logger.info("Ester proglotila direktoriyu i podumala: 'Massa znaniy! Sintez gotov.'")
                    # Integratsiya s self-evo i thinking
                    try:
                        from selfevo.evo_engine import start_evolution  # type: ignore
                        from thinking.think_core import init_thinking  # type: ignore
                        start_evolution(res.get("text", json.dumps(res)))  # Evolyutsiya
                        init_thinking(res.get("text", json.dumps(res)))  # Razmyshleniya
                        app.logger.info("Ester evolyutsionirovala i podumala nad bulk.")
                    except ImportError as e:
                        app.logger.warning(f"self-evo/thinking ne naydeny: {e}. Propuskaem.")
                    processed += 1
                    results.append(res)
                except Exception as e:
                    errors.append({"file": path, "error": str(e)})
        return jsonify(
            {
                "ok": True,
                "dir": root,
                "processed": processed,
                "skipped": skipped,
                "errors": errors,
                "results": results,
            }
        )  # <-- zakryvaem jsonify i sam return korrektno


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
def register(app):
    # calls an existing register_ingest_rutes(app) (url_prefix is ​​taken by default inside the function)
    return register_ingest_routes(app)

# === /AUTOSHIM ===