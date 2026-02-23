# -*- coding: utf-8 -*-
"""
messaging/email_smtp.py — SMTP-otpravka pisem + outbox-log (tablitsa mail_outbox).

MOSTY:
- (Yavnyy) send_email(to, subject, text=None, html=None) → {"sent":N,"failed":M,"by_recipient":[...]}.
- (Skrytyy #1) Avtovybor TLS/SMTPS po ENV (EMAIL_SMTP_STARTTLS) i logirovanie statusov/isklyucheniy.
- (Skrytyy #2) Ne trogaet suschestvuyuschiy outbox; sozdaet otdelnuyu mail_outbox (audit-friendly).

ZEMNOY ABZATs:
Ofitsialnaya i «tikhaya» dostavka pisem: korrektnye zagolovki, UTF-8, TLS, log statusov — udobno dlya retraev i audita.

# c=a+b
"""
from __future__ import annotations

import os, ssl, time, sqlite3, traceback
from typing import Any, Dict, List, Optional
from email.message import EmailMessage
import smtplib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB_PATH = os.getenv("MESSAGING_DB_PATH","data/messaging.db")

DDL = """
CREATE TABLE IF NOT EXISTS mail_outbox(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  recipient TEXT NOT NULL,
  subject TEXT NOT NULL,
  status TEXT NOT NULL,
  smtp_code INTEGER,
  smtp_err TEXT,
  message_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_mail_outbox_ts ON mail_outbox(ts DESC);
"""

def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=5.0, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(DDL)
    return c

def _smtp_client():
    host = os.getenv("EMAIL_SMTP_HOST","localhost")
    port = int(os.getenv("EMAIL_SMTP_PORT","587") or "587")
    starttls = (os.getenv("EMAIL_SMTP_STARTTLS","1") == "1")
    if not starttls and port == 465:
        return smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=15)
    s = smtplib.SMTP(host, port, timeout=15)
    s.ehlo()
    if starttls:
        s.starttls(context=ssl.create_default_context())
        s.ehlo()
    user = os.getenv("EMAIL_SMTP_USER") or ""
    pwd  = os.getenv("EMAIL_SMTP_PASS") or ""
    if user:
        s.login(user, pwd)
    return s

def _from_addr() -> str:
    name = os.getenv("EMAIL_DISPLAY_NAME","E.")
    addr = os.getenv("EMAIL_FROM_ADDR","ester@example.org")
    return f"{name} <{addr}>"

def _build_message(to: str, subject: str, text: Optional[str], html: Optional[str]) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = _from_addr()
    msg["To"] = to
    msg["Subject"] = subject
    if html and text:
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
    elif html:
        msg.add_alternative(html, subtype="html")
        # dobavim tekstovuyu vyzhimku
        msg.set_content((text or ""))
    else:
        msg.set_content(text or "")
    return msg

def _log(recipient: str, subject: str, status: str, code: Optional[int], err: Optional[str], msgid: Optional[str]):
    with _conn() as c:
        c.execute("INSERT INTO mail_outbox(ts,recipient,subject,status,smtp_code,smtp_err,message_id) VALUES(?,?,?,?,?,?,?)",
                  (time.time(), recipient, subject, status, int(code or 0), err or "", msgid or ""))

def send_email(to: List[str], subject: str, text: Optional[str] = None, html: Optional[str] = None) -> Dict[str, Any]:
    sent = 0; failed = 0; rows=[]
    if not to:
        return {"sent": 0, "failed": 0, "by_recipient": []}
    try:
        smtp = _smtp_client()
    except Exception as e:
        # ne mozhem soedinitsya — schitaem vse failed
        for r in to:
            _log(r, subject, "fail:connect", 0, str(e), None)
            rows.append({"to": r, "status": "fail:connect"})
        return {"sent": 0, "failed": len(to), "by_recipient": rows}

    for r in to:
        msg = _build_message(r, subject, text, html)
        try:
            resp = smtp.send_message(msg)
            # resp — dict {recipient: (code, resp_str)}
            code = 250; err = ""
            msgid = msg.get("Message-Id","")
            if isinstance(resp, dict) and r in resp and isinstance(resp[r], tuple):
                code = int(resp[r][0]); err = str(resp[r][1])
                if code >= 400:
                    failed += 1; _log(r, subject, "fail:smtp", code, err, msgid)
                    rows.append({"to": r, "status": "fail", "smtp_code": code, "smtp_err": err}); continue
            sent += 1; _log(r, subject, "ok", code, err, msgid)
            rows.append({"to": r, "status": "ok", "smtp_code": code})
        except smtplib.SMTPResponseException as e:
            failed += 1; _log(r, subject, "fail:smtp", int(getattr(e, "smtp_code", 0) or 0), str(getattr(e, "smtp_error","")), None)
            rows.append({"to": r, "status": "fail", "smtp_code": int(getattr(e,"smtp_code",0) or 0)})
        except Exception as e:
            failed += 1; _log(r, subject, "fail:exception", 0, str(e), None)
            rows.append({"to": r, "status": "fail", "error": str(e)})

    try:
        smtp.quit()
    except Exception:
        pass

    return {"sent": sent, "failed": failed, "by_recipient": rows}