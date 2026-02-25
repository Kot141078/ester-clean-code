# -*- coding: utf-8 -*-
from __future__ import annotations

"""modules/listeners/p2p_spooler.py - ochered P2P (Hive Mind) cherez Telegram-konverty.

Role:
- outbox → otpravka konvertov cherez Telegram
- vkhodyaschie Telegram updates → verify/HMAC → inbox (validnye) / failed (nevalidnye)
- inbox → apply_envelope_with_profile → arkhiv v sent or failed

Rezhimy:
- once (po umolchaniyu): odin tsikl send→poll→apply
- --loop: beskonechnyy tsikl s sleep(--interval)

AB_MODE:
- AB_MODE=A (po umolchaniyu) — dry-run pri apply (nothing ne menyaem, tolko logiruem)
- AB_MODE=B — realnoe primenenie konvertov

Printsipy:
- ne padat iz‑za odnogo plokhogo fayla ili odnogo plokhogo apdeyta;
- minimalnaya utechka detail naruzhu: oshibki logiruem, no tsikl prodolzhaem;
- bezopasnye imena faylov (bez path traversal/musora)."""

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from modules.transport.p2p_settings import load_settings  # type: ignore
from modules.transport.spool import ensure_dirs, list_queue, read_json, move  # type: ignore
from modules.transport.telegram_driver import send_envelope, poll_updates, verify_and_extract  # type: ignore
from modules.selfmanage.envelope_sync import apply_envelope_with_profile  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _ab_mode() -> str:
    ab = (os.getenv("AB_MODE") or "A").strip().upper()
    return "B" if ab == "B" else "A"


AB = _ab_mode()


_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


def _safe_id(x: Any, fallback: str = "x") -> str:
    s = str(x) if x is not None else ""
    s = s.strip()
    if not s:
        s = fallback
    s = _SAFE_ID_RE.sub("_", s)
    return s[:64]


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _send_all(settings: Dict[str, Any]) -> None:
    """Berem vse fayly iz outbox i pytaemsya otpravit.
    Uspekh → sent, inache → failed."""
    for p in list_queue("outbox"):
        try:
            env = read_json(p)
            if not env:
                move(p, "failed")
                continue

            rep = send_envelope(env, settings, ab_mode=AB)  # type: ignore[arg-type]
            if isinstance(rep, dict) and rep.get("ok"):
                move(p, "sent")
            else:
                move(p, "failed")
        except Exception:
            # Ne valim tsikl iz-za odnogo paketa
            try:
                move(p, "failed")
            except Exception:
                pass


def _poll_incoming(settings: Dict[str, Any]) -> None:
    """Pollim Telegram, checks the signature, put it in inbox/file."""
    try:
        rep = poll_updates(settings, ab_mode=AB)  # type: ignore[arg-type]
    except Exception:
        return

    if not isinstance(rep, dict) or not rep.get("ok"):
        return

    dirs = ensure_dirs() or {}
    inbox_dir = Path(dirs.get("inbox") or "state/p2p/inbox")
    failed_dir = Path(dirs.get("failed") or "state/p2p/failed")
    inbox_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    shared_key = str(settings.get("shared_key") or "")

    for u in rep.get("updates", []) or []:
        try:
            raw_text = (u.get("text") or "")
            ok, env = verify_and_extract(raw_text, shared_key)  # type: ignore[arg-type]

            ts = int(u.get("ts") or time.time())
            uid = _safe_id(u.get("id"), fallback="noid")
            name = f"{ts}_{uid}_p2p.json"

            if ok:
                fp = inbox_dir / name
                _write_json(fp, env)
            else:
                # podpis ne soshlas — intsident → failed
                fp = failed_dir / ("bad_" + name)
                _write_json(fp, {"bad": True, "ts": ts, "id": uid, "raw": raw_text})
        except Exception:
            # One broken update shouldn’t bring down everything
            try:
                ts = int(u.get("ts") or time.time())
                uid = _safe_id(u.get("id"), fallback="noid")
                fp = failed_dir / f"err_{ts}_{uid}_p2p.json"
                _write_json(fp, {"bad": True, "ts": ts, "id": uid, "raw": u.get("text")})
            except Exception:
                pass


def _apply_inbox(settings: Dict[str, Any]) -> None:
    """Primenyaem vkhodyaschie konverty.
    Uspekh → sent (arkhiv), inache → failed."""
    dry = (AB != "B")
    for p in list_queue("inbox"):
        try:
            env = read_json(p)
            if not env:
                move(p, "failed")
                continue

            payload = env.get("payload") or {}
            profile_id = payload.get("sync_profile_id") if isinstance(payload, dict) else None

            rep = apply_envelope_with_profile(env, profile_id, dry=dry)  # type: ignore[arg-type]

            # mini-log ryadom
            log_path = Path(p).with_suffix(".log.json")
            try:
                _write_json(log_path, {"ab": AB, "dry": dry, "result": rep})
            except Exception:
                pass

            if isinstance(rep, dict) and rep.get("ok"):
                move(p, "sent")
            else:
                move(p, "failed")
        except Exception:
            try:
                move(p, "failed")
            except Exception:
                pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ester P2P spooler (Telegram)")
    ap.add_argument("--loop", action="store_true", help="run forever")
    ap.add_argument("--interval", type=int, default=0, help="interval between cycles (sec)")
    args = ap.parse_args(argv)

    s = load_settings() or {}
    if not s.get("enable") or s.get("mode") != "telegram":
        print("[p2p] disabled", flush=True)
        return 0

    ensure_dirs()

    iv = int(args.interval or s.get("poll_interval") or 10)
    iv = max(3, iv)

    print(f"[p2p] start: mode=telegram ab={AB} loop={'on' if args.loop else 'off'} interval={iv}", flush=True)

    try:
        while True:
            _send_all(s)
            _poll_incoming(s)
            _apply_inbox(s)

            if not args.loop:
                break
            time.sleep(iv)
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())