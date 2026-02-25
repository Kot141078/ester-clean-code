# -*- coding: utf-8 -*-
"""modules/storage/uploader.py - universalnyy zagruzchik artefaktov na targety (local/s3/webdav/email).

Funktsii:
  • upload_file(target, file_path, dest_name=None) -> {"ok": True, "url": "..."} or {"ok": False, "error": "..."}
  • test_target(target) -> {"ok": True, ...} | {"ok": False, "error": "..."}

Dependency:
  - stdlib; optsionalno: boto3 (s3), requests (webdav). Esli modular net - akkuratno soobschaem."""

from __future__ import annotations

import os
import shutil
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# Optional dependencies - lazy loading
def _opt_import(name: str):
    try:
        return __import__(name)
    except Exception as e:
        return e


def _basename_no_dir(path: str) -> str:
    return os.path.basename(path.rstrip("/"))


# ---------- TEST ----------


def test_target(target: Dict[str, Any]) -> Dict[str, Any]:
    t = target or {}
    ttype = str(t.get("type") or "")
    if ttype == "local":
        path = os.path.abspath((t.get("config") or {}).get("path") or "")
        if not path:
            return {"ok": False, "error": "config.path required"}
        try:
            os.makedirs(path, exist_ok=True)
            test_file = os.path.join(path, ".ester_write_test")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(test_file)
            return {"ok": True, "path": path}
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    if ttype == "s3":
        boto3 = _opt_import("boto3")
        if isinstance(boto3, Exception):
            return {"ok": False, "error": "boto3 is required for s3"}
        cfg = t.get("config") or {}
        try:
            session = boto3.session.Session(
                aws_access_key_id=cfg.get("access_key") or None,
                aws_secret_access_key=cfg.get("secret_key") or None,
                region_name=cfg.get("region") or None,
            )
            s3 = session.resource("s3", endpoint_url=cfg.get("endpoint_url") or None)
            # Trying to get a bosquet (without creating)
            _ = s3.Bucket(cfg["bucket"]).creation_date
            return {"ok": True, "bucket": cfg["bucket"]}
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    if ttype == "webdav":
        requests = _opt_import("requests")
        if isinstance(requests, Exception):
            return {"ok": False, "error": "requests is required for webdav"}
        cfg = t.get("config") or {}
        url = cfg.get("url") or ""
        if not url:
            return {"ok": False, "error": "config.url required"}
        try:
            r = requests.head(url, auth=(cfg.get("username") or "", cfg.get("password") or ""))
            return {"ok": (200 <= r.status_code < 400), "status": r.status_code}
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    if ttype == "email":
        cfg = t.get("config") or {}
        try:
            with smtplib.SMTP(
                cfg.get("smtp_host"), int(cfg.get("smtp_port") or 587), timeout=10
            ) as s:
                if bool(cfg.get("use_tls", True)):
                    s.starttls()
                if cfg.get("username") and cfg.get("password"):
                    s.login(cfg["username"], cfg["password"])
                s.noop()
            return {"ok": True, "smtp": cfg.get("smtp_host")}
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    return {"ok": False, "error": f"unknown target type: {ttype}"}


# ---------- UPLOAD ----------


def upload_file(
    target: Dict[str, Any], file_path: str, dest_name: Optional[str] = None
) -> Dict[str, Any]:
    """Uploads the file to the target. Returns ZZF0Z or ZZF1ZZ."""
    t = target or {}
    ttype = str(t.get("type") or "")
    cfg = t.get("config") or {}
    src = os.path.abspath(file_path)
    if not os.path.exists(src):
        return {"ok": False, "error": "source file not found"}
    name = dest_name or _basename_no_dir(src)

    if ttype == "local":
        base = os.path.abspath(cfg.get("path") or "")
        if not base:
            return {"ok": False, "error": "config.path required"}
        try:
            os.makedirs(base, exist_ok=True)
            dst = os.path.join(base, name)
            shutil.copy2(src, dst)
            return {"ok": True, "url": f"file://{dst}"}
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    if ttype == "s3":
        boto3 = _opt_import("boto3")
        if isinstance(boto3, Exception):
            return {"ok": False, "error": "boto3 is required for s3"}
        try:
            session = boto3.session.Session(
                aws_access_key_id=cfg.get("access_key") or None,
                aws_secret_access_key=cfg.get("secret_key") or None,
                region_name=cfg.get("region") or None,
            )
            s3 = session.resource("s3", endpoint_url=cfg.get("endpoint_url") or None)
            bucket = s3.Bucket(cfg["bucket"])
            key = (cfg.get("prefix") or "") + name
            bucket.upload_file(src, key)
            base_url = cfg.get("public_url") or cfg.get("endpoint_url") or ""
            url = f"{base_url.rstrip('/')}/{cfg.get('bucket')}/{key}".replace("//", "/").replace(
                ":/", "://"
            )
            return {"ok": True, "url": url, "bucket": cfg.get("bucket"), "key": key}
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    if ttype == "webdav":
        requests = _opt_import("requests")
        if isinstance(requests, Exception):
            return {"ok": False, "error": "requests is required for webdav"}
        try:
            url = (cfg.get("url") or "").rstrip("/") + "/" + name
            with open(src, "rb") as f:
                r = requests.put(
                    url,
                    data=f,
                    auth=(cfg.get("username") or "", cfg.get("password") or ""),
                )
            return {
                "ok": (200 <= r.status_code < 400),
                "status": r.status_code,
                "url": url,
            }
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

    if ttype == "email":
        try:
            msg = EmailMessage()
            msg["From"] = cfg.get("from") or cfg.get("username")
            msg["To"] = ", ".join(cfg.get("to") or [cfg.get("from") or cfg.get("username")])
            msg["Date"] = formatdate(localtime=True)
            msg["Subject"] = f"[Ester Release] {name}"
            msg["Message-ID"] = make_msgid()
            msg.set_content("Artefakt reliza vo vlozhenii.\n\n— Ester")
            with open(src, "rb") as f:
                data = f.read()
            msg.add_attachment(data, maintype="application", subtype="zip", filename=name)

            with smtplib.SMTP(
                cfg.get("smtp_host"), int(cfg.get("smtp_port") or 587), timeout=30
            ) as s:
                if bool(cfg.get("use_tls", True)):
                    s.starttls()
                if cfg.get("username") and cfg.get("password"):
                    s.login(cfg["username"], cfg["password"])
                s.send_message(msg)
            return {"ok": True, "url": f"mailto:{msg['To']}"}
        except Exception as e:
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}

# return {"ok": False, "error": f"unknown target type: {ttype}"}