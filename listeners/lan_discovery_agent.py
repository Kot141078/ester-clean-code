# -*- coding: utf-8 -*-
from __future__ import annotations

"""modules/listeners/lan_discovery_agent.py - UDP-discovery sosedey po LAN (bez vneshnikh zavisimostey).

Role:
- periodicheski otpravlyaet broadcast UDP paket ("hello") s identifikatorom uzla i base_url;
- slushaet port i, poluchiv hello ot drugogo uzla, add/obnovlyaet peer registry.

Pochemu padalo/bylo khrupko:
- vnizu fayla byl sloman blok `if __name__ == "__main__":` → SyntaxError (expected an indented block). fileciteturn12file0
- beskonechnye tsikly bez stop_event i bez timeout na recvfrom meshayut shtatno ostanovit potok.
- secret klastera ranshe mog svetitsya v plaintext; add sovmestimyy HMAC-variant.

Sovmestimost:
- Esli ESTER_CLUSTER_SECRET empty → prinimaem lyubye hello (kak ranshe).
- Esli ESTER_CLUSTER_SECRET zadan:
  - prinimaem legacy: payload["secret"] == SECRET
  - i/ili newy variant: payload["sig"] (HMAC-SHA256) bez peredachi sekreta v soobschenii.
  - Esli khochesh ostavatsya strictly v legacy — postav ESTER_DISCOVERY_ACCEPT_HMAC=0

ENV:
- ESTER_DISCOVERY_PORT=53535
- ESTER_DISCOVERY_INTERVAL=5 (sek)
- ESTER_DISCOVERY_BIND=0.0.0.0
- ESTER_HTTP_BASE=http://127.0.0.1:8080
- ESTER_CLUSTER_SECRET=... (pusto = bez proverki)
- ESTER_DISCOVERY_BCAST=255.255.255.255 (mozhno: "255.255.255.255,192.168.1.255")
- ESTER_DISCOVERY_SEND_SECRET=0|1 (po umolchaniyu 0 — ne shlem secret, tolko HMAC)
- ESTER_DISCOVERY_ACCEPT_HMAC=0|1 (po umolchaniyu 1 — prinimaem HMAC)
- ESTER_DISCOVERY_RECV_TIMEOUT=1.0 (sek, chtoby stop_event rabotal)
- ESTER_DISCOVERY_TTL=0 (sek) okno validnosti dlya HMAC; 0 = ne proveryat vremya

MOSTY:
- Yavnyy: kibernetika ↔ svyaz: mayak "hello" + lokalnyy reestr → osnovanie dlya vybora transporta/marshruta.
- Skrytyy #1: infoteoriya ↔ minimalizm: UDP broadcast - minimum nakladnykh raskhodov, maximum shansov “uvidet” soseda.
- Skrytyy #2: bezopasnost ↔ avtonomnost: HMAC v stdlib vmesto vneshnego crypto-modulya + bez peredachi sekreta v pakete.

ZEMNOY ABZATs:
Eto kak morzyanka po provodam: “ya zdes, menya zovut tak-to, zhivu po etomu adresu.” This is enough,
chtoby nachat rabotu - i vazhno, chtoby “mayak” ne lomalsya iz-za odnoy krivoy stroki v __main__.

# c=a+b"""

import base64
import hashlib
import hmac
import json
import os
import socket
import sys
import threading
import time
from typing import Optional, Tuple

from modules.transport.peer_registry import set_self, upsert_peer  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PORT = int(os.getenv("ESTER_DISCOVERY_PORT", "53535"))
INTERVAL = max(1, int(os.getenv("ESTER_DISCOVERY_INTERVAL", "5")))
BIND = os.getenv("ESTER_DISCOVERY_BIND", "0.0.0.0")
BASE = os.getenv("ESTER_HTTP_BASE", f"http://127.0.0.1:{os.getenv('ESTER_PORT', '8090')}").strip()
SECRET = os.getenv("ESTER_CLUSTER_SECRET", "").strip()

BCASTS = [p.strip() for p in os.getenv("ESTER_DISCOVERY_BCAST", "255.255.255.255").split(",") if p.strip()]
SEND_SECRET = os.getenv("ESTER_DISCOVERY_SEND_SECRET", "0").strip() == "1"
ACCEPT_HMAC = os.getenv("ESTER_DISCOVERY_ACCEPT_HMAC", "1").strip() != "0"
RECV_TIMEOUT = float(os.getenv("ESTER_DISCOVERY_RECV_TIMEOUT", "1.0"))
TTL_SEC = int(os.getenv("ESTER_DISCOVERY_TTL", "0"))  # 0 = bez TTL


def _node_id() -> str:
    # Unikalnyy, no lokalnyy identifikator: host::user
    import getpass
    import platform

    return f"{platform.node()}::{getpass.getuser()}"


def _secret_key_bytes() -> bytes:
    """Podderzhka b64 klyuchey (optsionalno):
      - esli SECRET nachinaetsya s 'b64:' → decode base64
      - inache ispolzuem kak utf-8 bytes"""
    if not SECRET:
        return b""
    s = SECRET
    if s.startswith("b64:"):
        try:
            return base64.b64decode(s[4:].strip())
        except Exception:
            return s[4:].strip().encode("utf-8", errors="ignore")
    return s.encode("utf-8", errors="ignore")


def _make_sig(node_id: str, base_url: str, ts: int) -> str:
    """
    HMAC-SHA256 po stroke "node_id|base_url|ts" → hex.
    """
    key = _secret_key_bytes()
    raw = f"{node_id}|{base_url}|{ts}".encode("utf-8", errors="ignore")
    return hmac.new(key, raw, hashlib.sha256).hexdigest()


def _verify_sig(node_id: str, base_url: str, ts: int, sig: str) -> bool:
    if not SECRET:
        return True
    if not sig:
        return False
    if TTL_SEC > 0:
        now = int(time.time())
        if abs(now - int(ts)) > TTL_SEC:
            return False
    exp = _make_sig(node_id, base_url, int(ts))
    return hmac.compare_digest(exp, str(sig).strip().lower())


def _mk_socket() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # SO_REUSEPORT ne vezde, no poprobuem
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except Exception:
        pass
    # broadcast
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    # timeout so that the stop_event works (the receiver does not freeze forever)
    try:
        s.settimeout(max(0.2, float(RECV_TIMEOUT)))
    except Exception:
        pass
    return s


def sender(sock: socket.socket, node_id: str, stop: threading.Event) -> None:
    """
    Shlet hello po broadcast adresam.
    """
    while not stop.is_set():
        try:
            ts = int(time.time())
            payload = {"t": "hello", "node_id": node_id, "base_url": BASE, "ts": ts}
            if SECRET:
                if SEND_SECRET:
                    payload["secret"] = SECRET  # legacy
                if ACCEPT_HMAC:
                    payload["sig"] = _make_sig(node_id, BASE, ts)

            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

            for ip in BCASTS:
                try:
                    sock.sendto(data, (ip, PORT))
                except Exception:
                    continue
        except Exception:
            pass

        stop.wait(INTERVAL)


def receiver(sock: socket.socket, node_id: str, stop: threading.Event) -> None:
    """Listens to hello and updates the peer registers."""
    while not stop.is_set():
        try:
            try:
                buf, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue

            try:
                j = json.loads(buf.decode("utf-8", errors="replace"))
            except Exception:
                continue

            if not isinstance(j, dict) or j.get("t") != "hello":
                continue

            peer_id = str(j.get("node_id") or "").strip()
            if not peer_id or peer_id == node_id:
                continue

            base = str(j.get("base_url") or "").strip()
            if not base:
                continue

            # secret policy
            if SECRET:
                # legacy accept
                if str(j.get("secret") or "") == SECRET:
                    ok = True
                else:
                    ok = False
                    if ACCEPT_HMAC:
                        try:
                            ts = int(j.get("ts") or 0)
                        except Exception:
                            ts = 0
                        sig = str(j.get("sig") or "")
                        ok = bool(ts) and _verify_sig(peer_id, base, ts, sig)
                if not ok:
                    continue

            upsert_peer(peer_id, base, via="lan", secret_ok=bool(SECRET))
        except Exception:
            # best-effort: discovery should not crash the system
            continue


def main(argv: Optional[list[str]] = None) -> int:
    node = _node_id()
    set_self(node, BASE)

    s = _mk_socket()
    try:
        s.bind((BIND, PORT))
    except Exception:
        print(f"Cannot bind {BIND}:{PORT}", file=sys.stderr)
        return 1

    stop = threading.Event()

    th_rx = threading.Thread(target=receiver, args=(s, node, stop), daemon=True, name="lan-discovery-rx")
    th_tx = threading.Thread(target=sender, args=(s, node, stop), daemon=True, name="lan-discovery-tx")
    th_rx.start()
    th_tx.start()

    try:
        # keep the main thread alive
        while th_rx.is_alive() and th_tx.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        try:
            s.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())